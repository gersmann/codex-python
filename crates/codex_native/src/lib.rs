use anyhow::{Context, Result};
use codex_core::config::{find_codex_home, Config, ConfigOverrides, ConfigToml};
use codex_core::protocol::{EventMsg, InputItem};
use codex_core::{AuthManager, ConversationManager};
// use of SandboxMode is handled within core::config; not needed here
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyList, PyModule, PyString};
use serde_json::Value as JsonValue;
use std::path::PathBuf;
use std::sync::{mpsc, Arc, Mutex};
use std::thread;

#[pyfunction]
fn run_exec_collect(
    py: Python<'_>,
    prompt: String,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<Vec<Py<PyAny>>> {
    // Build a pure-Rust Config while holding the GIL
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;

    // Execute the conversation on a Tokio runtime
    let rt = tokio::runtime::Runtime::new().map_err(to_py)?;
    let events: Vec<JsonValue> = rt
        .block_on(async move { run_exec_impl(prompt, config).await })
        .map_err(to_py)?;

    // Convert serde_json::Value -> PyObject
    let mut out: Vec<Py<PyAny>> = Vec::with_capacity(events.len());
    for v in events {
        let obj = json_to_py(py, &v)?;
        out.push(obj);
    }
    Ok(out)
}

async fn run_exec_impl(prompt: String, config: Config) -> Result<Vec<JsonValue>> {
    let conversation_manager = ConversationManager::new(AuthManager::shared(
        config.codex_home.clone(),
        config.preferred_auth_method,
    ));
    let new_conv = conversation_manager.new_conversation(config).await?;
    let conversation = new_conv.conversation.clone();

    // submit prompt
    let _id = conversation
        .submit(codex_core::protocol::Op::UserInput {
            items: vec![InputItem::Text { text: prompt }],
        })
        .await?;

    // Collect events until TaskComplete or ShutdownComplete
    let mut out = Vec::new();
    loop {
        match conversation.next_event().await {
            Ok(ev) => {
                let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                out.push(serde_json::to_value(&ev)?);
                if is_complete {
                    // Ask the agent to shutdown; collect remaining events
                    let _ = conversation.submit(codex_core::protocol::Op::Shutdown).await;
                }
                if is_shutdown {
                    break;
                }
            }
            Err(_) => break,
        }
    }
    Ok(out)
}

fn to_py<E: std::fmt::Display>(e: E) -> PyErr {
    pyo3::exceptions::PyRuntimeError::new_err(e.to_string())
}

#[pyclass]
struct CodexEventStream {
    rx: Arc<Mutex<mpsc::Receiver<JsonValue>>>,
}

#[pymethods]
impl CodexEventStream {
    fn __iter__(slf: PyRefMut<'_, Self>) -> PyRefMut<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> Option<Py<PyAny>> {
        // Run the blocking recv without holding the GIL
        let res = py.detach(|| self.rx.lock().ok()?.recv().ok());
        match res {
            Some(v) => json_to_py(py, &v).ok(),
            None => None,
        }
    }
}

#[pyfunction]
fn start_exec_stream(
    prompt: String,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<CodexEventStream> {
    let (tx, rx) = mpsc::channel::<JsonValue>();

    // Build a pure-Rust Config on the Python thread
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let prompt_clone = prompt.clone();

    thread::spawn(move || {
        if let Err(e) = run_exec_stream_impl(prompt_clone, config, tx) {
            eprintln!("codex_native stream error: {e}");
        }
    });
    Ok(CodexEventStream {
        rx: Arc::new(Mutex::new(rx)),
    })
}

#[pymodule]
fn codex_native(_py: Python<'_>, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_exec_collect, m)?)?;
    m.add_function(wrap_pyfunction!(start_exec_stream, m)?)?;
    m.add_function(wrap_pyfunction!(preview_config, m)?)?;
    Ok(())
}

fn json_to_py(py: Python<'_>, v: &JsonValue) -> PyResult<Py<PyAny>> {
    let obj = match v {
        JsonValue::Null => py.None().clone_ref(py).into_any(),
        JsonValue::Bool(b) => {
            // Fallback to calling builtins.bool to obtain an owned bool object
            let builtins = PyModule::import(py, "builtins")?;
            let res = builtins.getattr("bool")?.call1((*b,))?;
            res.unbind().into_any()
        }
        JsonValue::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_pyobject(py)?.unbind().into_any().into()
            } else if let Some(u) = n.as_u64() {
                u.into_pyobject(py)?.unbind().into_any().into()
            } else if let Some(f) = n.as_f64() {
                PyFloat::new(py, f).into_pyobject(py)?.into_any().into()
            } else {
                py.None().into_pyobject(py)?.unbind().into_any().into()
            }
        }
        JsonValue::String(s) => PyString::new(py, s).into_pyobject(py)?.into_any().into(),
        JsonValue::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                let val = json_to_py(py, item)?;
                list.append(val.bind(py))?;
            }
            list.into_pyobject(py)?.into_any().into()
        }
        JsonValue::Object(map) => {
            let dict = PyDict::new(py);
            for (k, val) in map.iter() {
                let v = json_to_py(py, val)?;
                dict.set_item(k, v.bind(py))?;
            }
            dict.into_pyobject(py)?.into_any().into()
        }
    };
    Ok(obj)
}

fn build_config(
    overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> Result<Config> {
    let mut overrides_struct = ConfigOverrides::default();
    if let Some(dict) = overrides {
        if let Some(model) = dict.get_item("model")? {
            overrides_struct.model = Some(model.extract()?);
        }
        if let Some(provider) = dict.get_item("model_provider")? {
            overrides_struct.model_provider = Some(provider.extract()?);
        }
        if let Some(profile) = dict.get_item("config_profile")? {
            overrides_struct.config_profile = Some(profile.extract()?);
        }
        if let Some(policy) = dict.get_item("approval_policy")? {
            let policy_str: String = policy.extract()?;
            overrides_struct.approval_policy = Some(
                serde_json::from_str(&format!("\"{}\"", policy_str))
                    .context("invalid approval_policy")?,
            );
        }
        if let Some(sandbox) = dict.get_item("sandbox_mode")? {
            let sandbox_str: String = sandbox.extract()?;
            overrides_struct.sandbox_mode = Some(
                serde_json::from_str(&format!("\"{}\"", sandbox_str))
                    .context("invalid sandbox_mode")?,
            );
        }
        if let Some(cwd) = dict.get_item("cwd")? {
            overrides_struct.cwd = Some(PathBuf::from(cwd.extract::<String>()?));
        }
        if let Some(sandbox_exe) = dict.get_item("codex_linux_sandbox_exe")? {
            overrides_struct.codex_linux_sandbox_exe =
                Some(PathBuf::from(sandbox_exe.extract::<String>()?));
        }
        if let Some(bi) = dict.get_item("base_instructions")? {
            overrides_struct.base_instructions = Some(bi.extract()?);
        }
        if let Some(v) = dict.get_item("include_plan_tool")? {
            overrides_struct.include_plan_tool = Some(v.extract()?);
        }
        if let Some(v) = dict.get_item("include_apply_patch_tool")? {
            overrides_struct.include_apply_patch_tool = Some(v.extract()?);
        }
        if let Some(v) = dict.get_item("include_view_image_tool")? {
            overrides_struct.include_view_image_tool = Some(v.extract()?);
        }
        if let Some(v) = dict.get_item("show_raw_agent_reasoning")? {
            overrides_struct.show_raw_agent_reasoning = Some(v.extract()?);
        }
        if let Some(v) = dict.get_item("tools_web_search_request")? {
            overrides_struct.tools_web_search_request = Some(v.extract()?);
        }
    }

    if load_default_config {
        Ok(Config::load_with_cli_overrides(vec![], overrides_struct)?)
    } else {
        let codex_home = find_codex_home()?;
        Ok(Config::load_from_base_config_with_overrides(
            ConfigToml::default(),
            overrides_struct,
            codex_home,
        )?)
    }
}

fn run_exec_stream_impl(prompt: String, config: Config, tx: mpsc::Sender<JsonValue>) -> Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async move {
        let conversation_manager = ConversationManager::new(AuthManager::shared(
            config.codex_home.clone(),
            config.preferred_auth_method,
        ));
        let new_conv = conversation_manager.new_conversation(config).await?;
        let conversation = new_conv.conversation.clone();

        // submit prompt
        let _ = conversation
            .submit(codex_core::protocol::Op::UserInput {
                items: vec![InputItem::Text { text: prompt }],
            })
            .await?;

        loop {
            match conversation.next_event().await {
                Ok(ev) => {
                    let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                    let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                    let _ = tx.send(serde_json::to_value(&ev)?);
                    if is_complete {
                        let _ = conversation.submit(codex_core::protocol::Op::Shutdown).await;
                    }
                    if is_shutdown {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
        Ok::<(), anyhow::Error>(())
    })?;
    Ok(())
}

#[pyfunction]
fn preview_config(
    py: Python<'_>,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<Py<PyAny>> {
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;

    // Build a compact JSON map with fields useful for tests and introspection.
    let mut m = serde_json::Map::new();
    m.insert("model".to_string(), JsonValue::String(config.model.clone()));
    m.insert(
        "model_provider_id".to_string(),
        JsonValue::String(config.model_provider_id.clone()),
    );
    m.insert(
        "approval_policy".to_string(),
        JsonValue::String(format!("{}", config.approval_policy)),
    );
    let sandbox_mode_str = match &config.sandbox_policy {
        codex_core::protocol::SandboxPolicy::DangerFullAccess => "danger-full-access",
        codex_core::protocol::SandboxPolicy::ReadOnly => "read-only",
        codex_core::protocol::SandboxPolicy::WorkspaceWrite { .. } => "workspace-write",
    };
    m.insert(
        "sandbox_mode".to_string(),
        JsonValue::String(sandbox_mode_str.to_string()),
    );
    m.insert(
        "cwd".to_string(),
        JsonValue::String(config.cwd.display().to_string()),
    );
    m.insert(
        "include_plan_tool".to_string(),
        JsonValue::Bool(config.include_plan_tool),
    );
    m.insert(
        "include_apply_patch_tool".to_string(),
        JsonValue::Bool(config.include_apply_patch_tool),
    );
    m.insert(
        "include_view_image_tool".to_string(),
        JsonValue::Bool(config.include_view_image_tool),
    );
    m.insert(
        "show_raw_agent_reasoning".to_string(),
        JsonValue::Bool(config.show_raw_agent_reasoning),
    );
    m.insert(
        "tools_web_search_request".to_string(),
        JsonValue::Bool(config.tools_web_search_request),
    );

    let v = JsonValue::Object(m);
    json_to_py(py, &v)
}
