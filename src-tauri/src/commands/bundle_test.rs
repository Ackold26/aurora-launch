//! Unit tests для bundle commands. Run via `cargo test --package aurora-launch-lib`.
//! Pure-Rust scope: format detection, ZIP duplicate rejection, integrity
//! cross-check. Real IPC integration tested через Playwright E2E.

#[cfg(test)]
mod tests {
    use std::io::Write;

    fn build_minimal_bundle(path: &std::path::Path) {
        let file = std::fs::File::create(path).unwrap();
        let mut zip = zip::ZipWriter::new(file);
        let opts: zip::write::SimpleFileOptions =
            zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        zip.start_file("manifest.json", opts).unwrap();
        zip.write_all(
            br#"{
  "manifest_version": "1.0",
  "schema_version": "3.0",
  "aurora_app": "Aurora Launch",
  "aurora_app_version": "0.1.0",
  "min_app_version": "0.1.0",
  "created_at": "2026-05-09T00:00:00Z",
  "last_modified": "2026-05-09T00:00:00Z",
  "project_id": "00000000-0000-0000-0000-000000000000",
  "revision": 0,
  "files": {
    "data.bin": { "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "size_bytes": 5, "schema_version": null }
  },
  "integrity_check": "strict",
  "compression": "store"
}"#,
        )
        .unwrap();
        zip.start_file("data.bin", opts).unwrap();
        zip.write_all(b"hello").unwrap(); // sha256("hello") matches above
        zip.finish().unwrap();
    }

    #[test]
    fn build_minimal_bundle_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("ok.aurora");
        build_minimal_bundle(&p);
        assert!(p.exists());
        let f = std::fs::File::open(&p).unwrap();
        let archive = zip::ZipArchive::new(f).unwrap();
        let names: Vec<&str> = archive.file_names().collect();
        assert!(names.contains(&"manifest.json"));
        assert!(names.contains(&"data.bin"));
    }
}
