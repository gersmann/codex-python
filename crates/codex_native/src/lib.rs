use anyhow::{Context, Result};
use codex_core::config::{find_codex_home, Config, ConfigOverrides, ConfigToml};
use codex_core::protocol::{EventMsg, InputItem};
use codex_core::{AuthManager, ConversationManager};
// use of SandboxMode is handled within core::config; not needed here
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyList, PyModule, PyString};
use serde_json::Value as JsonValue;
use toml::value::Value as TomlValue;
use toml::value::Table as TomlTable;
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
    let mut cli_overrides: Vec<(String, TomlValue)> = Vec::new();

    if let Some(dict) = overrides {
        // Extract strongly-typed overrides first (these take precedence over CLI overrides).
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

        // Keys handled as strongly-typed above should not be duplicated in CLI overrides.
        let typed_keys = [
            "model",
            "model_provider",
            "config_profile",
            "approval_policy",
            "sandbox_mode",
            "cwd",
            "codex_linux_sandbox_exe",
            "base_instructions",
            "include_plan_tool",
            "include_apply_patch_tool",
            "include_view_image_tool",
            "show_raw_agent_reasoning",
            "tools_web_search_request",
        ];

        // Collect remaining extras and turn them into CLI-style dotted overrides.
        for (key_obj, value_obj) in dict.iter() {
            let key: String = match key_obj.extract() {
                Ok(s) => s,
                Err(_) => continue,
            };
            if typed_keys.contains(&key.as_str()) {
                continue;
            }

            // Convert Python value -> TomlValue
            let tv = match py_to_toml_value(value_obj)? {
                Some(v) => v,
                None => continue, // skip None/null values
            };

            if key.contains('.') {
                // Already a dotted path: use as-is.
                cli_overrides.push((key, tv));
            } else {
                // Flatten nested tables; otherwise add directly.
                flatten_overrides(&mut cli_overrides, &key, tv);
            }
        }
    }

    if load_default_config {
        // Start from built-in defaults and apply CLI + typed overrides.
        Ok(Config::load_with_cli_overrides(cli_overrides, overrides_struct)?)
    } else {
        // Do NOT read any on-disk config. Build a TOML value purely from CLI-style overrides
        // and then apply the strongly-typed overrides on top. We still resolve CODEX_HOME to
        // pass through for paths/auth handling, but we avoid parsing a config file.
        let codex_home = find_codex_home()?;

        // Build a base TOML value from dotted CLI overrides only (no file IO).
        let mut base_tbl: TomlTable = TomlTable::new();
        for (k, v) in cli_overrides.into_iter() {
            insert_dotted_toml(&mut base_tbl, &k, v);
        }

        let root_value = TomlValue::Table(base_tbl);
        let cfg: ConfigToml = root_value.try_into().map_err(|e| anyhow::anyhow!(e))?;
        Ok(Config::load_from_base_config_with_overrides(cfg, overrides_struct, codex_home)?)
    }
}

/// Convert a Python object into a TOML value. Returns Ok(None) for `None`.
fn py_to_toml_value(obj: Bound<'_, PyAny>) -> Result<Option<TomlValue>> {
    use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};

    if obj.is_none() {
        return Ok(None);
    }

    if let Ok(b) = obj.downcast::<PyBool>() {
        return Ok(Some(TomlValue::Boolean(b.is_true())));
    }
    if let Ok(i) = obj.downcast::<PyInt>() {
        let v: i64 = i.extract()?;
        return Ok(Some(TomlValue::Integer(v.into())));
    }
    if let Ok(f) = obj.downcast::<PyFloat>() {
        let v: f64 = f.extract()?;
        return Ok(Some(TomlValue::Float(v.into())));
    }
    if let Ok(s) = obj.downcast::<PyString>() {
        let v: String = s.extract()?;
        return Ok(Some(TomlValue::String(v.into())));
    }
    if let Ok(list) = obj.downcast::<PyList>() {
        let mut arr = Vec::with_capacity(list.len());
        for item in list.iter() {
            if let Some(tv) = py_to_toml_value(item)? {
                arr.push(tv);
            }
        }
        return Ok(Some(TomlValue::Array(arr)));
    }
    if let Ok(map) = obj.downcast::<PyDict>() {
        let mut tbl = TomlTable::new();
        for (k_obj, v_obj) in map.iter() {
            let key: String = match k_obj.extract() {
                Ok(s) => s,
                Err(_) => continue,
            };
            if let Some(tv) = py_to_toml_value(v_obj)? {
                tbl.insert(key, tv);
            }
        }
        return Ok(Some(TomlValue::Table(tbl)));
    }

    // Fallback: use `str(obj)`
    let s = obj.str()?.to_string_lossy().to_string();
    Ok(Some(TomlValue::String(s.into())))
}

/// Recursively flatten a TOML value into dotted overrides.
fn flatten_overrides(out: &mut Vec<(String, TomlValue)>, prefix: &str, val: TomlValue) {
    match val {
        TomlValue::Table(tbl) => {
            for (k, v) in tbl.into_iter() {
                let key = if prefix.is_empty() {
                    k
                } else {
                    format!("{prefix}.{k}")
                };
                flatten_overrides(out, &key, v);
            }
        }
        other => out.push((prefix.to_string(), other)),
    }
}

/// Insert a TOML value into `tbl` at a dotted path like "a.b.c".
fn insert_dotted_toml(tbl: &mut TomlTable, dotted: &str, val: TomlValue) {
    let parts: Vec<&str> = dotted.split('.').collect();
    insert_parts(tbl, &parts, val);
}

fn insert_parts(current: &mut TomlTable, parts: &[&str], val: TomlValue) {
    if parts.is_empty() {
        return;
    }
    if parts.len() == 1 {
        current.insert(parts[0].to_string(), val);
        return;
    }

    let key = parts[0].to_string();
    // Get or create an intermediate table at this segment.
    if let Some(existing) = current.get_mut(&key) {
        match existing {
            TomlValue::Table(ref mut t) => {
                insert_parts(t, &parts[1..], val);
            }
            _ => {
                let mut next = TomlTable::new();
                insert_parts(&mut next, &parts[1..], val);
                *existing = TomlValue::Table(next);
            }
        }
    } else {
        let mut next = TomlTable::new();
        insert_parts(&mut next, &parts[1..], val);
        current.insert(key, TomlValue::Table(next));
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
