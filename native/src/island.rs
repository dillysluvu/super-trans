//! Cầu nối IPC trực tiếp tới Quickshell/DMS cho Dynamic Island.
//!
//! DMS CLI (`dms ipc call ...`) rất tiện nhưng mỗi lần gọi lại khởi tạo một
//! tiến trình Go. Module này nói chuyện thẳng với Unix socket của Quickshell,
//! nên các thao tác publish/open/remove/poll chỉ mất vài mili-giây. Watcher
//! chạy bằng Rust cũng phản hồi nút bấm nhanh hơn nhiều so với vòng poll Python
//! (mỗi vòng phải spawn `dms`).
//!
//! Giao thức Quickshell IPC được giữ tương thích với:
//! https://github.com/quickshell-mirror/quickshell/blob/59e9c47/src/io/ipccomm.cpp

use serde_json::{json, Value};
use std::env;
use std::fs;
use std::io::{self, BufReader, Read, Write};
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant};

const COMMAND_STRING_CALL: u8 = 3;
const RESPONSE_NOT_READY: u8 = 1;
const RESPONSE_TARGET_NOT_FOUND: u8 = 2;
const RESPONSE_FUNCTION_NOT_FOUND: u8 = 3;
const RESPONSE_ARGUMENT_MISMATCH: u8 = 4;
const RESPONSE_COMPLETED: u8 = 5;
const MAX_STRING_LENGTH: usize = 1 << 20;
const MAX_PAYLOAD: usize = 64 * 1024;
const DEFAULT_DURATION_MS: u64 = 10_000;
const DEFAULT_POLL_MS: u64 = 80;
const MIN_POLL_MS: u64 = 40;
const MAX_POLL_MS: u64 = 1_000;
const READY_GRACE: Duration = Duration::from_secs(2);
const LIST_INTERVAL: Duration = Duration::from_secs(1);
const SOFT_GRACE: Duration = Duration::from_secs(10);
const MAX_LIFETIME: Duration = Duration::from_secs(600);
const MAX_CONSECUTIVE_ERRORS: u32 = 30;

pub fn usage(program: &str) {
    eprintln!("Cách dùng: {program} island <lệnh> [tham số]");
    eprintln!("  {program} island publish <source> <id>   (JSON payload qua stdin)");
    eprintln!("  {program} island open <source> <id>");
    eprintln!("  {program} island remove <source> <id>");
    eprintln!("  {program} island watch <source> <id> [--duration-ms N] [--poll-ms N]");
    eprintln!("  {program} island status");
    eprintln!("  {program} island call <target> <function> [args...]");
    eprintln!("  {program} capabilities");
}

pub fn run(args: &[String]) -> i32 {
    let Some(command) = args.first().map(String::as_str) else {
        usage("super-trans-native");
        return 2;
    };

    match command {
        "publish" => publish(&args[1..]),
        "open" => open(&args[1..]),
        "remove" => remove(&args[1..]),
        "watch" => watch(&args[1..]),
        "status" => status(),
        "call" => call_command(&args[1..]),
        "--help" | "-h" | "help" => {
            usage("super-trans-native");
            0
        }
        other => {
            eprintln!("Lệnh island không hợp lệ: {other}");
            usage("super-trans-native");
            2
        }
    }
}

pub fn capabilities() {
    println!(
        "{{\"chunk\":true,\"island\":true,\"ipc\":\"quickshell\",\"version\":\"{}\"}}",
        env!("CARGO_PKG_VERSION")
    );
}

fn publish(args: &[String]) -> i32 {
    if args.len() != 2 {
        eprintln!("Cần: island publish <source> <id>");
        return 2;
    }
    let source = &args[0];
    let id = &args[1];
    if !valid_id(source) || !valid_id(id) {
        eprintln!("source/id không hợp lệ (chỉ a-zA-Z0-9_.:-, tối đa 64 ký tự)");
        return 2;
    }

    let mut payload = String::new();
    if let Err(error) = io::stdin().read_to_string(&mut payload) {
        eprintln!("Không đọc được payload từ stdin: {error}");
        return 1;
    }
    let payload = payload.trim();
    if payload.is_empty() {
        eprintln!("Payload JSON rỗng.");
        return 1;
    }
    if payload.len() > MAX_PAYLOAD {
        eprintln!("Payload vượt quá {MAX_PAYLOAD} byte.");
        return 1;
    }
    if serde_json::from_str::<Value>(payload).is_err() {
        eprintln!("Payload không phải JSON hợp lệ.");
        return 1;
    }

    let response = match call_once("islandActivity", "publish", &[source, id, payload]) {
        Ok(value) => value,
        Err(error) => {
            eprintln!("Không publish được island: {error}");
            return 1;
        }
    };
    if !response.contains("ISLAND_ACTIVITY_PUBLISHED") {
        eprintln!("DMS từ chối activity: {response}");
        return 1;
    }

    let opened = call_once("islandActivity", "open", &[source, id])
        .map(|value| value.contains("ISLAND_ACTIVITY_OPENED"))
        .unwrap_or(false);

    println!("PUBLISHED=1");
    println!("OPENED={}", if opened { 1 } else { 0 });
    0
}

fn open(args: &[String]) -> i32 {
    if args.len() != 2 {
        eprintln!("Cần: island open <source> <id>");
        return 2;
    }
    match call_once("islandActivity", "open", &[&args[0], &args[1]]) {
        Ok(value) if value.contains("ISLAND_ACTIVITY_OPENED") => {
            println!("{value}");
            0
        }
        Ok(value) => {
            eprintln!("DMS không mở được activity: {value}");
            1
        }
        Err(error) => {
            eprintln!("Không mở được island: {error}");
            1
        }
    }
}

fn remove(args: &[String]) -> i32 {
    if args.len() != 2 {
        eprintln!("Cần: island remove <source> <id>");
        return 2;
    }
    match call_once("islandActivity", "remove", &[&args[0], &args[1]]) {
        Ok(value)
            if value.contains("ISLAND_ACTIVITY_REMOVED")
                || value.contains("ISLAND_ACTIVITY_NOT_FOUND") =>
        {
            println!("{value}");
            0
        }
        Ok(value) => {
            eprintln!("DMS không xóa được activity: {value}");
            1
        }
        Err(error) => {
            eprintln!("Không xóa được island: {error}");
            1
        }
    }
}

fn status() -> i32 {
    match call_once("island", "status", &[]) {
        Ok(value) => {
            println!("{value}");
            0
        }
        Err(error) => {
            eprintln!("Không đọc được trạng thái island: {error}");
            1
        }
    }
}

fn call_command(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("Cần: island call <target> <function> [args...]");
        return 2;
    }
    let target = &args[0];
    let function = &args[1];
    let call_args: Vec<&str> = args[2..].iter().map(String::as_str).collect();
    match call_once(target, function, &call_args) {
        Ok(value) => {
            println!("{value}");
            0
        }
        Err(error) => {
            eprintln!("IPC thất bại: {error}");
            1
        }
    }
}

fn watch(args: &[String]) -> i32 {
    if args.len() < 2 {
        eprintln!("Cần: island watch <source> <id> [--duration-ms N] [--poll-ms N]");
        return 2;
    }
    let source = &args[0];
    let id = &args[1];
    if !valid_id(source) || !valid_id(id) {
        eprintln!("source/id không hợp lệ.");
        return 2;
    }

    let mut duration_ms = DEFAULT_DURATION_MS;
    let mut poll_ms = DEFAULT_POLL_MS;
    let mut index = 2usize;
    while index < args.len() {
        match args[index].as_str() {
            "--duration-ms" => {
                let Some(value) = args.get(index + 1) else {
                    eprintln!("Thiếu giá trị sau --duration-ms");
                    return 2;
                };
                match value.parse::<u64>() {
                    Ok(parsed) => duration_ms = parsed.min(3_600_000),
                    Err(_) => {
                        eprintln!("--duration-ms phải là số nguyên");
                        return 2;
                    }
                }
                index += 2;
            }
            "--poll-ms" => {
                let Some(value) = args.get(index + 1) else {
                    eprintln!("Thiếu giá trị sau --poll-ms");
                    return 2;
                };
                match value.parse::<u64>() {
                    Ok(parsed) => {
                        poll_ms = parsed.clamp(MIN_POLL_MS, MAX_POLL_MS);
                    }
                    Err(_) => {
                        eprintln!("--poll-ms phải là số nguyên");
                        return 2;
                    }
                }
                index += 2;
            }
            other => {
                eprintln!("Tham số không hợp lệ: {other}");
                return 2;
            }
        }
    }

    let started = Instant::now();
    let duration = Duration::from_millis(duration_ms);
    let hard_deadline = started + MAX_LIFETIME;
    let soft_deadline = started + duration + SOFT_GRACE;
    let poll_interval = Duration::from_millis(poll_ms);
    let mut socket: Option<PathBuf> = None;
    let mut next_list = started;
    let mut list_readable = true;
    let mut ready = false;
    let mut consecutive_errors = 0u32;

    loop {
        let now = Instant::now();
        if now >= hard_deadline {
            let _ = call_with_socket(&mut socket, "islandActivity", "remove", &[source, id]);
            return 0;
        }

        match call_with_socket(&mut socket, "islandActivity", "pollActions", &[source]) {
            Ok(value) => {
                consecutive_errors = 0;
                if let Ok(events) = serde_json::from_str::<Value>(&value) {
                    if let Some(events) = events.as_array() {
                        for event in events {
                            let action = event.get("action").and_then(Value::as_str).unwrap_or("");
                            if action.is_empty() {
                                continue;
                            }
                            let payload = json!({
                                "type": "action",
                                "source": event
                                    .get("source")
                                    .and_then(Value::as_str)
                                    .unwrap_or(source),
                                "id": event
                                    .get("id")
                                    .and_then(Value::as_str)
                                    .unwrap_or(id),
                                "action": action,
                            });
                            if !emit_line(&payload.to_string()) {
                                return 0;
                            }
                        }
                    }
                }
            }
            Err(_) => {
                consecutive_errors += 1;
                if consecutive_errors > MAX_CONSECUTIVE_ERRORS {
                    return 1;
                }
            }
        }

        let now = Instant::now();
        if now >= next_list {
            match call_with_socket(&mut socket, "islandActivity", "list", &[]) {
                Ok(value) => {
                    list_readable = true;
                    let present = activity_present(&value, source, id);
                    if ready && !present {
                        return 0;
                    }
                    if !ready && present {
                        ready = true;
                        if !emit_line("{\"type\":\"ready\"}") {
                            return 0;
                        }
                    }
                }
                Err(_) => {
                    list_readable = false;
                }
            }
            next_list = Instant::now() + LIST_INTERVAL;
        }

        if !ready && started.elapsed() >= READY_GRACE {
            // Activity đã biến mất trước khi watcher kịp thấy nó.
            return 1;
        }
        if ready && !list_readable && now >= soft_deadline {
            return 0;
        }

        thread::sleep(poll_interval);
    }
}

fn activity_present(value: &str, source: &str, id: &str) -> bool {
    let Ok(entries) = serde_json::from_str::<Value>(value) else {
        return false;
    };
    let Some(entries) = entries.as_array() else {
        return false;
    };
    entries.iter().any(|entry| {
        entry.get("source").and_then(Value::as_str) == Some(source)
            && entry.get("id").and_then(Value::as_str) == Some(id)
    })
}

fn emit_line(line: &str) -> bool {
    let stdout = io::stdout();
    let mut handle = stdout.lock();
    if writeln!(handle, "{line}").is_err() {
        return false;
    }
    handle.flush().is_ok()
}

fn valid_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '.' | ':' | '-'))
}

fn call_once(target: &str, function: &str, args: &[&str]) -> Result<String, String> {
    let mut socket = None;
    call_with_socket(&mut socket, target, function, args)
}

fn call_with_socket(
    socket: &mut Option<PathBuf>,
    target: &str,
    function: &str,
    args: &[&str],
) -> Result<String, String> {
    if let Some(path) = socket.as_ref() {
        match ipc_call(path, target, function, args) {
            Ok(value) => return Ok(value),
            Err(_) => {
                *socket = None;
            }
        }
    }

    let path = discover_socket()?;
    let value = ipc_call(&path, target, function, args)?;
    *socket = Some(path);
    Ok(value)
}

fn discover_socket() -> Result<PathBuf, String> {
    let candidates = socket_candidates();
    if candidates.is_empty() {
        return Err("không tìm thấy socket Quickshell (DMS shell chưa chạy?)".to_string());
    }

    let mut last_error = String::new();
    for path in candidates {
        match ipc_call(&path, "islandActivity", "availability", &[]) {
            Ok(value) if value.contains("islandPresent") => return Ok(path),
            Ok(value) => last_error = format!("target không phù hợp: {value}"),
            Err(error) => last_error = error,
        }
    }
    Err(format!("không kết nối được Quickshell IPC: {last_error}"))
}

fn socket_candidates() -> Vec<PathBuf> {
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Some(value) = env::var_os("XDG_RUNTIME_DIR") {
        if !value.is_empty() {
            roots.push(PathBuf::from(value));
        }
    }
    if let Ok(entries) = fs::read_dir("/run/user") {
        for entry in entries.flatten() {
            roots.push(entry.path());
        }
    }
    roots.sort();
    roots.dedup();

    let mut sockets = Vec::new();
    for root in roots {
        let quickshell = root.join("quickshell");
        for subdir in ["by-pid", "by-id"] {
            let dir = quickshell.join(subdir);
            let Ok(entries) = fs::read_dir(dir) else {
                continue;
            };
            for entry in entries.flatten() {
                let path = entry.path().join("ipc.sock");
                if path.exists() {
                    sockets.push(path);
                }
            }
        }
    }
    sockets.sort();
    sockets.dedup();
    sockets
}

fn ipc_call(path: &Path, target: &str, function: &str, args: &[&str]) -> Result<String, String> {
    let mut stream = UnixStream::connect(path)
        .map_err(|error| format!("kết nối {}: {error}", path.display()))?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));

    let request = build_call(target, function, args)?;
    stream
        .write_all(&request)
        .map_err(|error| format!("ghi IPC: {error}"))?;

    let mut reader = BufReader::new(stream);
    let (value, is_void) = read_response(&mut reader)?;
    Ok(if is_void { String::new() } else { value })
}

fn build_call(target: &str, function: &str, args: &[&str]) -> Result<Vec<u8>, String> {
    let mut buffer = Vec::new();
    buffer.push(COMMAND_STRING_CALL);
    write_qstring(&mut buffer, target)?;
    write_qstring(&mut buffer, function)?;
    let count = u32::try_from(args.len()).map_err(|_| "quá nhiều tham số".to_string())?;
    buffer.extend_from_slice(&count.to_be_bytes());
    for arg in args {
        write_qstring(&mut buffer, arg)?;
    }
    Ok(buffer)
}

fn write_qstring(buffer: &mut Vec<u8>, value: &str) -> Result<(), String> {
    let encoded: Vec<u16> = value.encode_utf16().collect();
    let byte_length = encoded.len() * 2;
    if byte_length > MAX_STRING_LENGTH {
        return Err(format!("chuỗi IPC quá lớn: {byte_length} byte"));
    }
    buffer.extend_from_slice(&(byte_length as u32).to_be_bytes());
    for unit in encoded {
        buffer.extend_from_slice(&unit.to_be_bytes());
    }
    Ok(())
}

fn read_response<R: Read>(reader: &mut R) -> Result<(String, bool), String> {
    let mut index = [0u8; 1];
    reader
        .read_exact(&mut index)
        .map_err(|error| format!("đọc phản hồi IPC: {error}"))?;
    match index[0] {
        RESPONSE_NOT_READY => return Err("Quickshell IPC chưa sẵn sàng".to_string()),
        RESPONSE_TARGET_NOT_FOUND => return Err("không tìm thấy IPC target".to_string()),
        RESPONSE_FUNCTION_NOT_FOUND => return Err("không tìm thấy IPC function".to_string()),
        RESPONSE_ARGUMENT_MISMATCH => return Err("tham số IPC không khớp".to_string()),
        RESPONSE_COMPLETED => {}
        other => return Err(format!("phản hồi IPC không hỗ trợ: {other}")),
    }

    let mut is_void = [0u8; 1];
    reader
        .read_exact(&mut is_void)
        .map_err(|error| format!("đọc trạng thái IPC: {error}"))?;
    let value = read_qstring(reader)?;
    Ok((value, is_void[0] != 0))
}

fn read_qstring<R: Read>(reader: &mut R) -> Result<String, String> {
    let mut length_bytes = [0u8; 4];
    reader
        .read_exact(&mut length_bytes)
        .map_err(|error| format!("đọc độ dài QString: {error}"))?;
    let length = u32::from_be_bytes(length_bytes);
    if length == u32::MAX {
        return Ok(String::new());
    }
    if length as usize > MAX_STRING_LENGTH || length % 2 != 0 {
        return Err(format!("độ dài QString không hợp lệ: {length}"));
    }
    let mut units = Vec::with_capacity(length as usize / 2);
    for _ in 0..length / 2 {
        let mut unit = [0u8; 2];
        reader
            .read_exact(&mut unit)
            .map_err(|error| format!("đọc QString: {error}"))?;
        units.push(u16::from_be_bytes(unit));
    }
    String::from_utf16(&units).map_err(|error| format!("QString UTF-16 lỗi: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn qstring_roundtrip() {
        let mut buffer = Vec::new();
        write_qstring(&mut buffer, "é").unwrap();
        assert_eq!(buffer, vec![0, 0, 0, 2, 0x00, 0xE9]);
        let decoded = read_qstring(&mut Cursor::new(buffer)).unwrap();
        assert_eq!(decoded, "é");
    }

    #[test]
    fn call_wire_format_starts_with_call_and_count() {
        let buffer = build_call("spotlight", "toggle", &["true"]).unwrap();
        assert_eq!(buffer[0], COMMAND_STRING_CALL);
        assert!(buffer.windows(2).any(|window| window == [0x00, 0x74]));
        assert_eq!(&buffer[1..5], &[0, 0, 0, 18]);
        assert!(buffer.ends_with(&[0, 0, 0, 8, 0, 0x74, 0, 0x72, 0, 0x75, 0, 0x65]));
    }

    #[test]
    fn response_roundtrip() {
        let mut data = vec![RESPONSE_COMPLETED, 0];
        write_qstring(&mut data, "{\"ok\": true}").unwrap();
        let (value, is_void) = read_response(&mut Cursor::new(data)).unwrap();
        assert_eq!(value, "{\"ok\": true}");
        assert!(!is_void);
    }

    #[test]
    fn response_errors_are_reported() {
        for (index, expected) in [
            (RESPONSE_NOT_READY, "chưa sẵn sàng"),
            (RESPONSE_TARGET_NOT_FOUND, "target"),
            (RESPONSE_FUNCTION_NOT_FOUND, "function"),
            (RESPONSE_ARGUMENT_MISMATCH, "tham số"),
        ] {
            let error = read_response(&mut Cursor::new(vec![index])).unwrap_err();
            assert!(error.contains(expected), "{error}");
        }
    }

    #[test]
    fn activity_id_validation() {
        assert!(valid_id("supertrans-123-456"));
        assert!(valid_id("result.1:2_3"));
        assert!(!valid_id(""));
        assert!(!valid_id("has space"));
        assert!(!valid_id(&"x".repeat(65)));
    }

    #[test]
    fn activity_presence() {
        let value = r#"[{"source":"src","id":"id"}]"#;
        assert!(activity_present(value, "src", "id"));
        assert!(!activity_present(value, "src", "other"));
        assert!(!activity_present("not json", "src", "id"));
    }
}
