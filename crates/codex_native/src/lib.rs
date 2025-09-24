use anyhow::{Context, Result};
use codex_core::config::{find_codex_home, Config, ConfigOverrides, ConfigToml};
use codex_core::protocol::{Event, EventMsg, InputItem, Op, ReviewRequest};
use codex_core::{AuthManager, CodexAuth, ConversationManager};
// use of SandboxMode is handled within core::config; not needed here
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyFloat, PyInt, PyList, PyModule, PyString};
use serde_json::Value as JsonValue;
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::{mpsc, Arc, Mutex, Once};
use std::thread;
use toml::value::Table as TomlTable;
use toml::value::Value as TomlValue;

/// Local copy of the submit id used for the synthetic SessionConfigured event.
///
/// Upstream (`codex_core::codex::INITIAL_SUBMIT_ID`) is intentionally `pub(crate)`
/// and not accessible from this bridge crate. The current value is an empty
/// string; we mirror that here to keep wire compatibility without depending on
/// a private symbol.
const INITIAL_SUBMIT_ID: &str = "";

#[pyfunction(signature = (prompt, config_overrides=None, load_default_config=true, output_schema=None))]
fn run_exec_collect(
    py: Python<'_>,
    prompt: String,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
    output_schema: Option<Bound<'_, PyAny>>,
) -> PyResult<Vec<Py<PyAny>>> {
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let output_schema_json = match output_schema {
        Some(obj) if !obj.is_none() => Some(py_to_json_value(obj).map_err(to_py)?),
        _ => None,
    };

    let rt = tokio::runtime::Runtime::new().map_err(to_py)?;
    let events: Vec<JsonValue> = rt
        .block_on(async move { run_exec_impl(prompt, config, output_schema_json).await })
        .map_err(to_py)?;

    let mut out: Vec<Py<PyAny>> = Vec::with_capacity(events.len());
    for v in events {
        let obj = json_to_py(py, &v)?;
        out.push(obj);
    }
    Ok(out)
}

async fn run_exec_impl(
    prompt: String,
    config: Config,
    output_schema: Option<JsonValue>,
) -> Result<Vec<JsonValue>> {
    let config_clone = config.clone();
    let conversation_manager = match std::env::var("OPENAI_API_KEY") {
        Ok(val) if !val.trim().is_empty() => {
            ConversationManager::with_auth(CodexAuth::from_api_key(&val))
        }
        _ => ConversationManager::new(AuthManager::shared(config.codex_home.clone())),
    };
    let new_conv = conversation_manager.new_conversation(config).await?;
    let conversation = new_conv.conversation.clone();
    let session_event = Event {
        id: INITIAL_SUBMIT_ID.to_string(),
        msg: EventMsg::SessionConfigured(new_conv.session_configured),
    };
    let mut out = Vec::new();
    out.push(serde_json::to_value(&session_event)?);

    conversation
        .submit(Op::UserTurn {
            items: vec![InputItem::Text { text: prompt }],
            cwd: config_clone.cwd.clone(),
            approval_policy: config_clone.approval_policy,
            sandbox_policy: config_clone.sandbox_policy.clone(),
            model: config_clone.model.clone(),
            effort: config_clone.model_reasoning_effort,
            summary: config_clone.model_reasoning_summary,
            final_output_json_schema: output_schema,
        })
        .await?;

    loop {
        match conversation.next_event().await {
            Ok(ev) => {
                let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                out.push(serde_json::to_value(&ev)?);
                if is_complete {
                    // Ask the agent to shutdown; collect remaining events
                    let _ = conversation
                        .submit(codex_core::protocol::Op::Shutdown)
                        .await;
                }
                if is_shutdown {
                    break;
                }
            }
            Err(err) => return Err(err.into()),
        }
    }
    Ok(out)
}

fn to_py<E: std::fmt::Display>(e: E) -> PyErr {
    pyo3::exceptions::PyRuntimeError::new_err(e.to_string())
}

#[pyclass]
struct CodexEventStream {
    rx: Arc<Mutex<mpsc::Receiver<Result<JsonValue, String>>>>,
}

#[pymethods]
impl CodexEventStream {
    fn __iter__(slf: PyRefMut<'_, Self>) -> PyRefMut<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        // Run the blocking recv without holding the GIL
        let res = py.detach(|| self.rx.lock().ok().and_then(|rx| rx.recv().ok()));
        match res {
            Some(Ok(v)) => Ok(Some(json_to_py(py, &v)?)),
            Some(Err(msg)) => Err(pyo3::exceptions::PyRuntimeError::new_err(msg)),
            None => Ok(None),
        }
    }
}

#[pyfunction(signature = (prompt, config_overrides=None, load_default_config=true, output_schema=None))]
fn start_exec_stream(
    prompt: String,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
    output_schema: Option<Bound<'_, PyAny>>,
) -> PyResult<CodexEventStream> {
    let (tx, rx) = mpsc::channel::<Result<JsonValue, String>>();

    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let output_schema_json = match output_schema {
        Some(obj) if !obj.is_none() => Some(py_to_json_value(obj).map_err(to_py)?),
        _ => None,
    };
    let prompt_clone = prompt.clone();

    thread::spawn(move || {
        let tx_for_impl = tx.clone();
        if let Err(e) = run_exec_stream_impl(prompt_clone, config, output_schema_json, tx_for_impl)
        {
            let msg = e.to_string();
            let _ = tx.send(Err(msg.clone()));
            eprintln!("codex_native stream error: {msg}");
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
    m.add_function(wrap_pyfunction!(run_review_collect, m)?)?;
    m.add_function(wrap_pyfunction!(start_review_stream, m)?)?;
    m.add_function(wrap_pyfunction!(start_conversation, m)?)?;
    m.add_class::<NativeConversation>()?;
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

fn py_to_json_value(obj: Bound<'_, PyAny>) -> Result<JsonValue> {
    if obj.is_none() {
        return Ok(JsonValue::Null);
    }

    if let Ok(b) = obj.downcast::<PyBool>() {
        return Ok(JsonValue::Bool(b.is_true()));
    }
    if let Ok(i) = obj.downcast::<PyInt>() {
        let value: i64 = i.extract()?;
        return Ok(JsonValue::Number(value.into()));
    }
    if let Ok(f) = obj.downcast::<PyFloat>() {
        let value: f64 = f.extract()?;
        if let Some(number) = serde_json::Number::from_f64(value) {
            return Ok(JsonValue::Number(number));
        }
        return Ok(JsonValue::Null);
    }
    if let Ok(s) = obj.downcast::<PyString>() {
        let value: String = s.extract()?;
        if let Ok(parsed) = serde_json::from_str::<JsonValue>(&value) {
            return Ok(parsed);
        }
        return Ok(JsonValue::String(value));
    }
    if let Ok(list) = obj.downcast::<PyList>() {
        let mut arr = Vec::with_capacity(list.len());
        for item in list.iter() {
            arr.push(py_to_json_value(item)?);
        }
        return Ok(JsonValue::Array(arr));
    }
    if let Ok(dict) = obj.downcast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k_obj, v_obj) in dict.iter() {
            let key: String = match k_obj.extract() {
                Ok(s) => s,
                Err(_) => continue,
            };
            map.insert(key, py_to_json_value(v_obj)?);
        }
        return Ok(JsonValue::Object(map));
    }

    let text = obj.str()?.to_string_lossy().to_string();
    if let Ok(parsed) = serde_json::from_str::<JsonValue>(&text) {
        return Ok(parsed);
    }
    Ok(JsonValue::String(text))
}

fn build_config(overrides: Option<Bound<'_, PyDict>>, load_default_config: bool) -> Result<Config> {
    // Match CLI behavior: import env vars from ~/.codex/.env (if present)
    // before reading config/auth so OPENAI_API_KEY and friends are visible.
    // Security: filter out CODEX_* variables just like the CLI does.
    static LOAD_DOTENV_ONCE: Once = Once::new();
    LOAD_DOTENV_ONCE.call_once(|| load_dotenv());

    let mut overrides_struct = ConfigOverrides::default();
    let mut cli_overrides: Vec<(String, TomlValue)> = Vec::new();

    if let Some(dict) = overrides {
        // Single-pass: handle typed keys and collect remaining extras as CLI-style overrides.
        for (key_obj, value_obj) in dict.iter() {
            let key: String = match key_obj.extract() {
                Ok(s) => s,
                Err(_) => continue,
            };

            match key.as_str() {
                // Strongly-typed overrides
                "model" => {
                    overrides_struct.model = Some(value_obj.extract()?);
                }
                "review_model" => {
                    overrides_struct.review_model = Some(value_obj.extract()?);
                }
                "model_provider" => {
                    overrides_struct.model_provider = Some(value_obj.extract()?);
                }
                "config_profile" => {
                    overrides_struct.config_profile = Some(value_obj.extract()?);
                }
                "approval_policy" => {
                    let s: String = value_obj.extract()?;
                    // Avoid building an extra quoted string; parse via a JSON string value.
                    overrides_struct.approval_policy = Some(
                        serde_json::from_value(JsonValue::String(s))
                            .context("invalid approval_policy")?,
                    );
                }
                "sandbox_mode" => {
                    let s: String = value_obj.extract()?;
                    overrides_struct.sandbox_mode = Some(
                        serde_json::from_value(JsonValue::String(s))
                            .context("invalid sandbox_mode")?,
                    );
                }
                "cwd" => {
                    overrides_struct.cwd = Some(PathBuf::from(value_obj.extract::<String>()?));
                }
                "codex_linux_sandbox_exe" => {
                    overrides_struct.codex_linux_sandbox_exe =
                        Some(PathBuf::from(value_obj.extract::<String>()?));
                }
                "base_instructions" => {
                    overrides_struct.base_instructions = Some(value_obj.extract()?);
                }
                "include_plan_tool" => {
                    overrides_struct.include_plan_tool = Some(value_obj.extract()?);
                }
                "include_apply_patch_tool" => {
                    overrides_struct.include_apply_patch_tool = Some(value_obj.extract()?);
                }
                "include_view_image_tool" => {
                    overrides_struct.include_view_image_tool = Some(value_obj.extract()?);
                }
                "show_raw_agent_reasoning" => {
                    overrides_struct.show_raw_agent_reasoning = Some(value_obj.extract()?);
                }
                "tools_web_search_request" => {
                    overrides_struct.tools_web_search_request = Some(value_obj.extract()?);
                }
                // Everything else becomes a CLI-style override (supports dotted keys and tables)
                _ => {
                    let tv = match py_to_toml_value(value_obj)? {
                        Some(v) => v,
                        None => continue, // skip None/null values
                    };
                    if key.contains('.') {
                        cli_overrides.push((key, tv));
                    } else {
                        flatten_overrides(&mut cli_overrides, &key, tv);
                    }
                }
            }
        }
    }

    if load_default_config {
        // Start from built-in defaults and apply CLI + typed overrides.
        Ok(Config::load_with_cli_overrides(
            cli_overrides,
            overrides_struct,
        )?)
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
        Ok(Config::load_from_base_config_with_overrides(
            cfg,
            overrides_struct,
            codex_home,
        )?)
    }
}

const ILLEGAL_ENV_VAR_PREFIX: &str = "CODEX_";

/// Load env vars from ~/.codex/.env, filtering out any keys that start with
/// CODEX_ (reserved for internal use). This mirrors the behavior in the
/// `codex-arg0` crate used by the CLI so python users get the same DX.
fn load_dotenv() {
    if let Ok(codex_home) = find_codex_home() {
        let env_path = codex_home.join(".env");
        if let Ok(iter) = dotenvy::from_path_iter(env_path) {
            set_filtered(iter);
        }
    }
}

/// Helper to set vars from a dotenvy iterator while filtering out `CODEX_` keys.
fn set_filtered<I>(iter: I)
where
    I: IntoIterator<Item = Result<(String, String), dotenvy::Error>>,
{
    for (key, value) in iter.into_iter().flatten() {
        if !key.to_ascii_uppercase().starts_with(ILLEGAL_ENV_VAR_PREFIX) {
            // Safe to modify env here – we do it up front before we spawn runtimes/threads.
            unsafe { std::env::set_var(&key, &value) };
        }
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

fn run_exec_stream_impl(
    prompt: String,
    config: Config,
    output_schema: Option<JsonValue>,
    tx: mpsc::Sender<Result<JsonValue, String>>,
) -> Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async move {
        let config_clone = config.clone();
        let conversation_manager = match std::env::var("OPENAI_API_KEY") {
            Ok(val) if !val.trim().is_empty() => {
                ConversationManager::with_auth(CodexAuth::from_api_key(&val))
            }
            _ => ConversationManager::new(AuthManager::shared(config.codex_home.clone())),
        };
        let new_conv = conversation_manager.new_conversation(config).await?;
        let conversation = new_conv.conversation.clone();
        let session_event = Event {
            id: INITIAL_SUBMIT_ID.to_string(),
            msg: EventMsg::SessionConfigured(new_conv.session_configured),
        };
        let session_json = serde_json::to_value(&session_event)?;
        if tx.send(Ok(session_json)).is_err() {
            return Ok(());
        }

        conversation
            .submit(Op::UserTurn {
                items: vec![InputItem::Text { text: prompt }],
                cwd: config_clone.cwd.clone(),
                approval_policy: config_clone.approval_policy,
                sandbox_policy: config_clone.sandbox_policy.clone(),
                model: config_clone.model.clone(),
                effort: config_clone.model_reasoning_effort,
                summary: config_clone.model_reasoning_summary,
                final_output_json_schema: output_schema,
            })
            .await?;

        loop {
            match conversation.next_event().await {
                Ok(ev) => {
                    let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                    let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                    let event_json = serde_json::to_value(&ev)?;
                    if tx.send(Ok(event_json)).is_err() {
                        break;
                    }
                    if is_complete {
                        let _ = conversation
                            .submit(codex_core::protocol::Op::Shutdown)
                            .await;
                    }
                    if is_shutdown {
                        break;
                    }
                }
                Err(err) => {
                    let _ = tx.send(Err(err.to_string()));
                    return Err(err.into());
                }
            }
        }
        Ok::<(), anyhow::Error>(())
    })?;
    Ok(())
}

#[pyfunction(signature = (prompt, user_facing_hint=None, config_overrides=None, load_default_config=true))]
fn run_review_collect(
    py: Python<'_>,
    prompt: String,
    user_facing_hint: Option<String>,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<Vec<Py<PyAny>>> {
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let hint = user_facing_hint;
    let rt = tokio::runtime::Runtime::new().map_err(to_py)?;
    let events: Vec<JsonValue> = rt
        .block_on(async move { run_review_impl(prompt, hint, config).await })
        .map_err(to_py)?;

    let mut out: Vec<Py<PyAny>> = Vec::with_capacity(events.len());
    for v in events {
        let obj = json_to_py(py, &v)?;
        out.push(obj);
    }
    Ok(out)
}

async fn run_review_impl(
    prompt: String,
    user_facing_hint: Option<String>,
    config: Config,
) -> Result<Vec<JsonValue>> {
    let conversation_manager = match std::env::var("OPENAI_API_KEY") {
        Ok(val) if !val.trim().is_empty() => {
            ConversationManager::with_auth(CodexAuth::from_api_key(&val))
        }
        _ => ConversationManager::new(AuthManager::shared(config.codex_home.clone())),
    };
    let new_conv = conversation_manager.new_conversation(config).await?;
    let conversation = new_conv.conversation.clone();
    let session_event = Event {
        id: INITIAL_SUBMIT_ID.to_string(),
        msg: EventMsg::SessionConfigured(new_conv.session_configured),
    };
    let mut out = Vec::new();
    out.push(serde_json::to_value(&session_event)?);

    let hint = user_facing_hint.unwrap_or_else(|| prompt.clone());
    let review_request = ReviewRequest {
        prompt,
        user_facing_hint: hint,
    };

    conversation.submit(Op::Review { review_request }).await?;

    loop {
        match conversation.next_event().await {
            Ok(ev) => {
                let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                out.push(serde_json::to_value(&ev)?);
                if is_complete {
                    let _ = conversation
                        .submit(codex_core::protocol::Op::Shutdown)
                        .await;
                }
                if is_shutdown {
                    break;
                }
            }
            Err(err) => return Err(err.into()),
        }
    }
    Ok(out)
}

#[pyfunction(signature = (prompt, user_facing_hint=None, config_overrides=None, load_default_config=true))]
fn start_review_stream(
    prompt: String,
    user_facing_hint: Option<String>,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<CodexEventStream> {
    let (tx, rx) = mpsc::channel::<Result<JsonValue, String>>();

    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let prompt_clone = prompt.clone();

    thread::spawn(move || {
        let tx_for_impl = tx.clone();
        if let Err(e) = run_review_stream_impl(prompt_clone, user_facing_hint, config, tx_for_impl)
        {
            let msg = e.to_string();
            let _ = tx.send(Err(msg.clone()));
            eprintln!("codex_native stream error: {msg}");
        }
    });
    Ok(CodexEventStream {
        rx: Arc::new(Mutex::new(rx)),
    })
}

fn run_review_stream_impl(
    prompt: String,
    user_facing_hint: Option<String>,
    config: Config,
    tx: mpsc::Sender<Result<JsonValue, String>>,
) -> Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async move {
        let conversation_manager = match std::env::var("OPENAI_API_KEY") {
            Ok(val) if !val.trim().is_empty() => {
                ConversationManager::with_auth(CodexAuth::from_api_key(&val))
            }
            _ => ConversationManager::new(AuthManager::shared(config.codex_home.clone())),
        };
        let new_conv = conversation_manager.new_conversation(config).await?;
        let conversation = new_conv.conversation.clone();
        let session_event = Event {
            id: INITIAL_SUBMIT_ID.to_string(),
            msg: EventMsg::SessionConfigured(new_conv.session_configured),
        };
        let session_json = serde_json::to_value(&session_event)?;
        if tx.send(Ok(session_json)).is_err() {
            return Ok(());
        }

        let hint = user_facing_hint.unwrap_or_else(|| prompt.clone());
        let review_request = ReviewRequest {
            prompt,
            user_facing_hint: hint,
        };

        conversation.submit(Op::Review { review_request }).await?;

        loop {
            match conversation.next_event().await {
                Ok(ev) => {
                    let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
                    let is_complete = matches!(ev.msg, EventMsg::TaskComplete(_));
                    let event_json = serde_json::to_value(&ev)?;
                    if tx.send(Ok(event_json)).is_err() {
                        break;
                    }
                    if is_complete {
                        let _ = conversation
                            .submit(codex_core::protocol::Op::Shutdown)
                            .await;
                    }
                    if is_shutdown {
                        break;
                    }
                }
                Err(err) => {
                    let msg = err.to_string();
                    let _ = tx.send(Err(msg));
                    return Err(err.into());
                }
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

// ===== New: Stateful Conversation API =====

use codex_core::protocol::{AskForApproval, ReviewDecision, SandboxPolicy};
use codex_core::protocol_config_types::{ReasoningEffort, ReasoningSummary};

#[pyclass]
struct NativeConversation {
    rt: Arc<tokio::runtime::Runtime>,
    conversation: Arc<codex_core::CodexConversation>,
    pending: Arc<Mutex<VecDeque<JsonValue>>>,
    closed: Arc<Mutex<bool>>,
    defaults: Arc<Mutex<TurnDefaults>>,
}

struct TurnDefaults {
    cwd: PathBuf,
    approval_policy: AskForApproval,
    sandbox_policy: SandboxPolicy,
    model: String,
    effort: Option<ReasoningEffort>,
    summary: ReasoningSummary,
}

#[pymethods]
impl NativeConversation {
    fn __iter__(slf: PyRefMut<'_, Self>) -> PyRefMut<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        // Serve queued events (SessionConfigured) first
        if let Ok(mut q) = self.pending.lock() {
            if let Some(v) = q.pop_front() {
                return json_to_py(py, &v).map(Some);
            }
        }
        if let Ok(closed) = self.closed.lock() {
            if *closed {
                return Ok(None);
            }
        }

        let ev = self
            .rt
            .block_on(async { self.conversation.next_event().await })
            .map_err(to_py)?;

        let is_shutdown = matches!(ev.msg, EventMsg::ShutdownComplete);
        if is_shutdown {
            if let Ok(mut c) = self.closed.lock() {
                *c = true;
            }
        }
        let v = serde_json::to_value(&ev).map_err(to_py)?;
        json_to_py(py, &v).map(Some)
    }

    /// Submit a user turn (single text prompt) with optional per-turn overrides.
    #[pyo3(signature = (prompt, *, cwd=None, approval_policy=None, sandbox_mode=None, model=None, effort=None, summary=None, output_schema=None))]
    fn submit_user_turn(
        &self,
        prompt: String,
        cwd: Option<String>,
        approval_policy: Option<String>,
        sandbox_mode: Option<String>,
        model: Option<String>,
        effort: Option<String>,
        summary: Option<String>,
        output_schema: Option<Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let output_schema_json = match output_schema {
            Some(obj) if !obj.is_none() => Some(py_to_json_value(obj).map_err(to_py)?),
            _ => None,
        };

        // Compute effective values from stored defaults + provided overrides.
        let mut d = self
            .defaults
            .lock()
            .map_err(|_| to_py("defaults poisoned"))?;

        let cwd_path = cwd.map(PathBuf::from).unwrap_or_else(|| d.cwd.clone());
        let approval_eff = match approval_policy {
            Some(s) => parse_approval(&s)?,
            None => d.approval_policy,
        };
        let sandbox_eff = match sandbox_mode {
            Some(s) => parse_sandbox(&s)?,
            None => d.sandbox_policy.clone(),
        };
        let model_eff = model.unwrap_or_else(|| d.model.clone());
        let effort_eff: Option<ReasoningEffort> = match effort {
            Some(s) => Some(parse_effort(&s)?),
            None => d.effort,
        };
        let summary_eff: ReasoningSummary = match summary {
            Some(s) => parse_summary(&s)?,
            None => d.summary,
        };

        self.rt
            .block_on(async {
                self.conversation
                    .submit(Op::UserTurn {
                        items: vec![InputItem::Text { text: prompt }],
                        cwd: cwd_path.clone(),
                        approval_policy: approval_eff,
                        sandbox_policy: sandbox_eff.clone(),
                        model: model_eff.clone(),
                        effort: effort_eff,
                        summary: summary_eff,
                        final_output_json_schema: output_schema_json,
                    })
                    .await
                    .map_err(|e| anyhow::anyhow!(e))
            })
            .map_err(to_py)?;

        // Persist new defaults for subsequent turns.
        d.cwd = cwd_path;
        d.approval_policy = approval_eff;
        d.sandbox_policy = sandbox_eff;
        d.model = model_eff;
        d.effort = effort_eff;
        d.summary = summary_eff;
        Ok(())
    }

    /// Enter review mode with an optional user-facing hint.
    #[pyo3(signature = (prompt, user_facing_hint=None))]
    fn submit_review(&self, prompt: String, user_facing_hint: Option<String>) -> PyResult<()> {
        let review_request = ReviewRequest {
            prompt,
            user_facing_hint: user_facing_hint.unwrap_or_default(),
        };
        self.rt
            .block_on(async { self.conversation.submit(Op::Review { review_request }).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Approve or deny an exec request (id from EventMsg::ExecApprovalRequest)
    fn approve_exec(&self, id: String, decision: String) -> PyResult<()> {
        let d = parse_review_decision(&decision)?;
        self.rt
            .block_on(async { self.conversation.submit(Op::ExecApproval { id, decision: d }).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Approve or deny an apply-patch request (id from EventMsg::ApplyPatchApprovalRequest)
    fn approve_patch(&self, id: String, decision: String) -> PyResult<()> {
        let d = parse_review_decision(&decision)?;
        self.rt
            .block_on(async { self.conversation.submit(Op::PatchApproval { id, decision: d }).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Interrupt the current task (same effect as sending Op::Interrupt).
    fn interrupt(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::Interrupt).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Ask the agent to shutdown; iteration will end after ShutdownComplete.
    fn shutdown(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::Shutdown).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Inject user input into the current task (does not create a new turn).
    fn user_input_text(&self, text: String) -> PyResult<()> {
        self.rt
            .block_on(async {
                self.conversation
                    .submit(Op::UserInput {
                        items: vec![InputItem::Text { text }],
                    })
                    .await
            })
            .map_err(to_py)?;
        Ok(())
    }

    /// Override persistent turn context for subsequent turns (no input sent).
    #[pyo3(signature = (cwd=None, approval_policy=None, sandbox_mode=None, model=None, effort=None, clear_effort=false, summary=None))]
    fn override_turn_context(
        &self,
        cwd: Option<String>,
        approval_policy: Option<String>,
        sandbox_mode: Option<String>,
        model: Option<String>,
        effort: Option<String>,
        clear_effort: bool,
        summary: Option<String>,
    ) -> PyResult<()> {
        let eff_effort: Option<Option<ReasoningEffort>> = if clear_effort {
            Some(None)
        } else if let Some(e) = effort {
            Some(Some(parse_effort(&e)?))
        } else {
            None
        };
        let approval = match approval_policy {
            Some(s) => Some(parse_approval(&s)?),
            None => None,
        };
        let sandbox = match sandbox_mode {
            Some(s) => Some(parse_sandbox(&s)?),
            None => None,
        };
        let cwd_path = cwd.map(PathBuf::from);
        let summary_eff = match summary {
            Some(s) => Some(parse_summary(&s)?),
            None => None,
        };

        self.rt
            .block_on(async {
                self.conversation
                    .submit(Op::OverrideTurnContext {
                        cwd: cwd_path,
                        approval_policy: approval,
                        sandbox_policy: sandbox,
                        model,
                        effort: eff_effort,
                        summary: summary_eff,
                    })
                    .await
            })
            .map_err(to_py)?;
        Ok(())
    }

    /// Append an entry to the persisted cross-session history.
    fn add_to_history(&self, text: String) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::AddToHistory { text }).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Request a history entry by (log_id, offset). Reply comes as EventMsg::GetHistoryEntryResponse.
    fn get_history_entry(&self, log_id: u64, offset: usize) -> PyResult<()> {
        self.rt
            .block_on(async {
                self.conversation
                    .submit(Op::GetHistoryEntryRequest { offset, log_id })
                    .await
            })
            .map_err(to_py)?;
        Ok(())
    }

    /// Ask the agent to emit ConversationHistory for the current session.
    fn get_path(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::GetPath).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Request list of MCP tools; reply is EventMsg::McpListToolsResponse.
    fn list_mcp_tools(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::ListMcpTools).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Request list of custom prompts; reply is EventMsg::ListCustomPromptsResponse.
    fn list_custom_prompts(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::ListCustomPrompts).await })
            .map_err(to_py)?;
        Ok(())
    }

    /// Request the agent to summarize/compact context.
    fn compact(&self) -> PyResult<()> {
        self.rt
            .block_on(async { self.conversation.submit(Op::Compact).await })
            .map_err(to_py)?;
        Ok(())
    }
}

#[pyfunction(signature = (config_overrides=None, load_default_config=true))]
fn start_conversation(
    _py: Python<'_>,
    config_overrides: Option<Bound<'_, PyDict>>,
    load_default_config: bool,
) -> PyResult<NativeConversation> {
    let config = build_config(config_overrides, load_default_config).map_err(to_py)?;
    let defaults_seed = config.clone();

    let rt = tokio::runtime::Runtime::new().map_err(to_py)?;
    let conversation_manager = match std::env::var("OPENAI_API_KEY") {
        Ok(val) if !val.trim().is_empty() => ConversationManager::with_auth(CodexAuth::from_api_key(&val)),
        _ => ConversationManager::new(AuthManager::shared(config.codex_home.clone())),
    };
    let new_conv = rt
        .block_on(async { conversation_manager.new_conversation(config).await })
        .map_err(to_py)?;
    let conversation = new_conv.conversation.clone();

    // Seed initial SessionConfigured event so iterator users always see it first.
    let session_event = Event {
        id: INITIAL_SUBMIT_ID.to_string(),
        msg: EventMsg::SessionConfigured(new_conv.session_configured),
    };
    let mut q = VecDeque::new();
    q.push_back(serde_json::to_value(&session_event).map_err(to_py)?);

    // Initialize per-turn defaults from the session config provided to new_conversation
    // We don't have direct access to all fields here (approval/sandbox), but they
    // originate from the provided Config.
    let defaults = TurnDefaults {
        cwd: defaults_seed.cwd.clone(),
        approval_policy: defaults_seed.approval_policy,
        sandbox_policy: defaults_seed.sandbox_policy.clone(),
        model: defaults_seed.model.clone(),
        effort: defaults_seed.model_reasoning_effort,
        summary: defaults_seed.model_reasoning_summary,
    };

    Ok(NativeConversation {
        rt: Arc::new(rt),
        conversation,
        pending: Arc::new(Mutex::new(q)),
        closed: Arc::new(Mutex::new(false)),
        defaults: Arc::new(Mutex::new(defaults)),
    })
}

fn parse_review_decision(s: &str) -> PyResult<ReviewDecision> {
    match s {
        "approved" => Ok(ReviewDecision::Approved),
        "approved_for_session" | "approved-for-session" => Ok(ReviewDecision::ApprovedForSession),
        "denied" => Ok(ReviewDecision::Denied),
        "abort" => Ok(ReviewDecision::Abort),
        _ => Err(to_py("invalid decision; expected approved|approved_for_session|denied|abort")),
    }
}

fn parse_approval(s: &str) -> PyResult<AskForApproval> {
    serde_json::from_value(JsonValue::String(s.to_string())).map_err(|_| to_py("invalid approval_policy"))
}

fn parse_sandbox(s: &str) -> PyResult<SandboxPolicy> {
    match s {
        "danger-full-access" => Ok(SandboxPolicy::DangerFullAccess),
        "read-only" => Ok(SandboxPolicy::ReadOnly),
        "workspace-write" => Ok(SandboxPolicy::WorkspaceWrite {
            writable_roots: vec![],
            network_access: false,
            exclude_tmpdir_env_var: false,
            exclude_slash_tmp: false,
        }),
        _ => Err(to_py("invalid sandbox_mode")),
    }
}

fn parse_effort(s: &str) -> PyResult<ReasoningEffort> {
    serde_json::from_value(JsonValue::String(s.to_string())).map_err(|_| to_py("invalid reasoning effort"))
}

fn parse_summary(s: &str) -> PyResult<ReasoningSummary> {
    serde_json::from_value(JsonValue::String(s.to_string())).map_err(|_| to_py("invalid reasoning summary"))
}

// (Removed unused default helpers; protocol and config already provide sensible defaults.)
