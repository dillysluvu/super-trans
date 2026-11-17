//! SuperTrans Native Helper
//!
//! Chia văn bản dài thành các đoạn <= giới hạn ký tự, ưu tiên ranh giới
//! xuống dòng > cuối câu > khoảng trắng > cắt cứng. Thuật toán phản chiếu
//! `FastEngine.split_text` trong Python nhưng chạy bằng Rust cho văn bản lớn.
//!
//! Giao thức: đọc UTF-8 từ stdin, ghi các đoạn phân tách bằng ký tự NUL ra stdout.

use std::io::{self, Read, Write};
use std::process;

mod island;

const DEFAULT_LIMIT: usize = 1800;

fn split_text(text: &str, limit: usize) -> Vec<String> {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Vec::new();
    }

    let chars: Vec<char> = trimmed.chars().collect();
    if chars.len() <= limit {
        return vec![chars.iter().collect()];
    }

    let mut chunks: Vec<String> = Vec::new();
    let mut start = 0usize;
    let half = limit / 2;

    while start < chars.len() {
        if chars.len() - start <= limit {
            let chunk: String = chars[start..].iter().collect();
            let chunk = chunk.trim();
            if !chunk.is_empty() {
                chunks.push(chunk.to_string());
            }
            break;
        }

        let end = start + limit;
        let mut cut: Option<usize> = None;

        // 1. Ưu tiên xuống dòng.
        for index in (start..end).rev() {
            if chars[index] == '\n' {
                cut = Some(index);
                break;
            }
        }

        // 2. Cuối câu (dấu câu + khoảng trắng hoặc hết cửa sổ).
        if cut.map_or(true, |value| value < start + half) {
            let mut sentence_cut: Option<usize> = None;
            for index in start..end {
                if matches!(chars[index], '.' | '!' | '?' | '。' | '！' | '？') {
                    let next = if index + 1 < end {
                        Some(chars[index + 1])
                    } else {
                        None
                    };
                    if next.map_or(true, |ch| ch.is_whitespace()) {
                        let after = if index + 1 < end {
                            index + 2
                        } else {
                            index + 1
                        };
                        sentence_cut = Some(after);
                    }
                }
            }
            cut = sentence_cut;
        }

        // 3. Khoảng trắng gần nhất.
        if cut.map_or(true, |value| value < start + half) {
            cut = None;
            for index in (start..end).rev() {
                if chars[index] == ' ' {
                    cut = Some(index);
                    break;
                }
            }
        }

        // 4. Cắt cứng.
        let cut = match cut {
            Some(value) if value >= start + half => value,
            _ => end,
        };

        let chunk: String = chars[start..cut].iter().collect();
        let chunk = chunk.trim();
        if !chunk.is_empty() {
            chunks.push(chunk.to_string());
        }

        start = cut;
        while start < chars.len() && chars[start].is_whitespace() {
            start += 1;
        }
    }

    chunks
}

fn usage(program: &str) {
    eprintln!("Cách dùng: {program} chunk [--limit N]");
    eprintln!("           {program} island <lệnh> [tham số]");
    eprintln!("           {program} capabilities");
    eprintln!("           {program} --version");
    eprintln!("Đọc văn bản UTF-8 từ stdin, ghi các đoạn phân tách bằng NUL.");
    island::usage(program);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let program = args
        .first()
        .map(String::as_str)
        .unwrap_or("super-trans-native");

    if args.len() < 2 {
        usage(program);
        process::exit(2);
    }

    match args[1].as_str() {
        "--version" | "version" => {
            println!("super-trans-native {}", env!("CARGO_PKG_VERSION"));
            return;
        }
        "capabilities" => {
            island::capabilities();
            return;
        }
        "island" => {
            process::exit(island::run(&args[2..]));
        }
        "chunk" => {}
        "--help" | "-h" | "help" => {
            usage(program);
            return;
        }
        other => {
            eprintln!("Lệnh không hợp lệ: {other}");
            usage(program);
            process::exit(2);
        }
    }

    let mut limit = DEFAULT_LIMIT;
    let mut index = 2usize;
    while index < args.len() {
        match args[index].as_str() {
            "--limit" => {
                if index + 1 >= args.len() {
                    eprintln!("Thiếu giá trị sau --limit");
                    process::exit(2);
                }
                match args[index + 1].parse::<usize>() {
                    Ok(value) if value > 0 => limit = value,
                    _ => {
                        eprintln!("--limit phải là số nguyên dương");
                        process::exit(2);
                    }
                }
                index += 2;
            }
            other => {
                eprintln!("Tham số không hợp lệ: {other}");
                usage(program);
                process::exit(2);
            }
        }
    }

    let mut input = String::new();
    if let Err(error) = io::stdin().read_to_string(&mut input) {
        eprintln!("Không đọc được stdin: {error}");
        process::exit(2);
    }

    let chunks = split_text(&input, limit);
    let stdout = io::stdout();
    let mut handle = stdout.lock();

    for (position, chunk) in chunks.iter().enumerate() {
        if position > 0 {
            if let Err(error) = handle.write_all(b"\0") {
                eprintln!("Không ghi được stdout: {error}");
                process::exit(2);
            }
        }
        if let Err(error) = handle.write_all(chunk.as_bytes()) {
            eprintln!("Không ghi được stdout: {error}");
            process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::split_text;

    fn no_whitespace(text: &str) -> String {
        text.chars().filter(|ch| !ch.is_whitespace()).collect()
    }

    #[test]
    fn short_text_is_unchanged() {
        assert_eq!(split_text("  Hello world  ", 100), vec!["Hello world"]);
        assert!(split_text("   \n\t ", 100).is_empty());
    }

    #[test]
    fn chunks_respect_limit_and_preserve_content() {
        let samples = [
            "Hello world. ".repeat(300),
            "你好世界。".repeat(500),
            "Dòng một\nDòng hai\n".repeat(200),
            "x".repeat(5000),
            "Café crème à la française. ".repeat(300),
        ];

        for sample in samples {
            let chunks = split_text(&sample, 500);
            assert!(!chunks.is_empty());
            assert!(chunks.iter().all(|chunk| chunk.chars().count() <= 500));
            assert_eq!(no_whitespace(&sample), no_whitespace(&chunks.join("")),);
        }
    }

    #[test]
    fn prefers_paragraph_boundaries() {
        let chunks = split_text("Đoạn một.\nĐoạn hai.\nĐoạn ba.", 12);
        assert_eq!(chunks[0], "Đoạn một.");
        assert!(chunks.len() > 1);
    }
}
