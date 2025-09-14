use anyhow::{anyhow, Context, Result};
use clap::Parser;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Generate a JSON Schema for the Codex protocol types by:
/// 1) Ensuring TypeScript bindings are generated via the upstream generator
/// 2) Running `ts-json-schema-generator` to emit a combined schema
#[derive(Parser, Debug)]
#[command(about = "Generate JSON Schema for Codex protocol types")]
struct Args {
    /// Output directory for the generated TypeScript declarations (.generated/ts by default)
    #[arg(long = "ts-out", value_name = "DIR", default_value = ".generated/ts")]
    ts_out: PathBuf,

    /// Output directory for the generated JSON Schema (.generated/schema by default)
    #[arg(long = "schema-out", value_name = "DIR", default_value = ".generated/schema")]
    schema_out: PathBuf,

    /// Optional path to the Prettier binary to format emitted TS (forwarded to upstream generator)
    #[arg(long = "prettier", value_name = "PRETTIER_BIN")]
    prettier: Option<PathBuf>,
}

fn main() -> Result<()> {
    let args = Args::parse();

    // 1) Ensure TS bindings exist by delegating to the upstream TS generator.
    // Prefer using the checked-in monorepo under codex-proj/codex-rs; fall back to a global 'codex generate-ts'.
    ensure_ts_generated(&args.ts_out, args.prettier.as_deref())?;

    // 2) Ensure a minimal tsconfig.json alongside the generated TS files.
    let tsconfig_path = write_tsconfig_if_missing(&args.ts_out)?;

    // 3) Run ts-json-schema-generator via npx to emit a combined schema for all exported types.
    let schema_path = args.schema_out.join("protocol.schema.json");
    fs::create_dir_all(&args.schema_out)
        .with_context(|| format!("Failed to create output dir {}", args.schema_out.display()))?;
    run_typescript_json_schema(&tsconfig_path, &schema_path)?;

    println!("Wrote {}", schema_path.display());
    Ok(())
}

fn ensure_ts_generated(ts_out: &Path, prettier: Option<&Path>) -> Result<()> {
    if ts_out.is_dir() {
        // Assume caller wants to reuse existing output if present.
        return Ok(());
    }
    fs::create_dir_all(ts_out)
        .with_context(|| format!("Failed to create TS output dir {}", ts_out.display()))?;

    // Try invoking the local workspace generator: `cd codex-proj/codex-rs && cargo run -p codex-protocol-ts`.
    let monorepo = Path::new("codex-proj").join("codex-rs");
    if monorepo.is_dir() {
        let mut cmd = Command::new("cargo");
        cmd.arg("run")
            .arg("-p")
            .arg("codex-protocol-ts")
            .arg("--")
            .arg("--out")
            .arg(relative_path_from(&monorepo, ts_out)?)
            .current_dir(&monorepo);
        if let Some(bin) = prettier {
            cmd.arg("--prettier").arg(relative_path_from(&monorepo, bin)?);
        }
        let status = cmd.status().context("Failed to run codex-protocol-ts generator")?;
        if status.success() {
            return Ok(());
        }
    }

    // Fallback: attempt `codex generate-ts` if available.
    let status = Command::new("codex")
        .arg("generate-ts")
        .arg("--out")
        .arg(ts_out)
        .status();
    match status {
        Ok(s) if s.success() => Ok(()),
        _ => Err(anyhow!(
            "Failed to generate TS types; ensure either codex-proj/codex-rs exists or 'codex generate-ts' is available"
        )),
    }
}

fn write_tsconfig_if_missing(ts_out: &Path) -> Result<PathBuf> {
    let tsconfig_path = ts_out.join("tsconfig.json");
    if tsconfig_path.exists() {
        return Ok(tsconfig_path);
    }
    let contents = r#"{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["./**/*.ts"]
}
"#;
    fs::write(&tsconfig_path, contents).with_context(|| {
        format!(
            "Failed to write tsconfig.json to {}",
            tsconfig_path.display()
        )
    })?;
    Ok(tsconfig_path)
}

fn run_typescript_json_schema(tsconfig_path: &Path, schema_path: &Path) -> Result<()> {
    // Use ts-json-schema-generator which supports `bigint`, unlike typescript-json-schema.
    // We point it at all generated .ts files and request a schema for all exported types ("*").
    let npx = which::which("npx")
        .map_err(|_| anyhow!("'npx' not found in PATH; please install Node.js (>=18)"))?;

    let ts_dir = tsconfig_path
        .parent()
        .ok_or_else(|| anyhow!("invalid tsconfig path"))?;
    let glob = ts_dir.join("*.ts");

    let status = Command::new(npx)
        .arg("--yes")
        .arg("ts-json-schema-generator@1.5.1")
        .arg("--path")
        .arg(glob)
        .arg("--type")
        .arg("*")
        .arg("--expose")
        .arg("all")
        .arg("--additional-properties")
        .arg("--out")
        .arg(schema_path)
        .status()
        .context("Failed to invoke ts-json-schema-generator via npx")?;
    if !status.success() {
        return Err(anyhow!(
            "ts-json-schema-generator failed; verify TypeScript files compile and Node.js is available"
        ));
    }
    Ok(())
}

// Build a relative path from `base` the working dir of a spawned command to `target`.
fn relative_path_from(base: &Path, target: &Path) -> Result<PathBuf> {
    let abs_base = fs::canonicalize(base).with_context(|| format!("canon {}", base.display()))?;
    let abs_target = fs::canonicalize(target).unwrap_or_else(|_| target.to_path_buf());
    pathdiff::diff_paths(abs_target, abs_base)
        .ok_or_else(|| anyhow!("Failed to compute relative path"))
}
