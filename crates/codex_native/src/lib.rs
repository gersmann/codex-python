use pyo3::prelude::*;

/// Lightweight wheel-tag shim.
///
/// The Python SDK runtime now uses the bundled `codex` CLI binary directly, but we keep a
/// minimal abi3 extension so maturin can produce platform-tagged wheels that bundle the right
/// native executable per target.
#[pymodule]
fn codex_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
