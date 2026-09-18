use std::collections::BTreeMap;
use std::env;
use std::fmt;
use std::fs;
use std::io::{self, Read};
use std::process;

// ---------------------------------------------------------------------------
// JSON value (for grammar deserialisation + token value serialisation)
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
enum V {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(#[allow(dead_code)] Vec<V>),
    Obj(BTreeMap<String, V>),
}

// ---------------------------------------------------------------------------
// Minimal JSON parser -- we only need to round-trip the grammar.json subset
// that src/core/grammar.json produces.
// ---------------------------------------------------------------------------

struct Jp<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Jp<'a> {
    fn new(b: &'a [u8]) -> Self {
        Self { b, i: 0 }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn ws(&mut self) {
        while let Some(c) = self.peek() {
            if c != b' ' && c != b'\t' && c != b'\n' && c != b'\r' {
                break;
            }
            self.i += 1;
        }
    }

    fn eat(&mut self, c: u8) -> Result<(), String> {
        if self.peek() == Some(c) {
            self.i += 1;
            Ok(())
        } else {
            Err(format!(
                "expected '{}' at pos {}, found {:?}",
                c as char,
                self.i,
                self.peek().map(|b| b as char)
            ))
        }
    }

    fn value(&mut self) -> Result<V, String> {
        self.ws();
        match self.peek().ok_or("unexpected end of JSON")? {
            b'{' => self.obj(),
            b'[' => self.arr(),
            b'"' => self.str().map(V::Str),
            b't' => self.literal(b"true", V::Bool(true)),
            b'f' => self.literal(b"false", V::Bool(false)),
            b'n' => self.literal(b"null", V::Null),
            _ => self.num(),
        }
    }

    fn obj(&mut self) -> Result<V, String> {
        self.eat(b'{')?;
        let mut m = BTreeMap::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(V::Obj(m));
        }
        loop {
            self.ws();
            let k = self.str()?;
            self.eat(b':')?;
            let v = self.value()?;
            m.insert(k, v);
            self.ws();
            match self.peek() {
                Some(b'}') => {
                    self.i += 1;
                    break;
                }
                Some(b',') => {
                    self.i += 1;
                }
                _ => return Err("expected ',' or '}' in object".into()),
            }
        }
        Ok(V::Obj(m))
    }

    fn arr(&mut self) -> Result<V, String> {
        self.eat(b'[')?;
        let mut v = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(V::Arr(v));
        }
        loop {
            v.push(self.value()?);
            self.ws();
            match self.peek() {
                Some(b']') => {
                    self.i += 1;
                    break;
                }
                Some(b',') => {
                    self.i += 1;
                }
                _ => return Err("expected ',' or ']' in array".into()),
            }
        }
        Ok(V::Arr(v))
    }

    fn str(&mut self) -> Result<String, String> {
        self.eat(b'"')?;
        let mut out = Vec::new();
        loop {
            match self.peek().ok_or("unterminated string")? {
                b'"' => {
                    self.i += 1;
                    return String::from_utf8(out).map_err(|e| format!("invalid utf-8: {e}"));
                }
                b'\\' => {
                    self.i += 1;
                    match self.peek().ok_or("unterminated escape")? {
                        b'"' => out.push(b'"'),
                        b'\\' => out.push(b'\\'),
                        b'/' => out.push(b'/'),
                        b'b' => out.push(0x08),
                        b'f' => out.push(0x0C),
                        b'n' => out.push(b'\n'),
                        b'r' => out.push(b'\r'),
                        b't' => out.push(b'\t'),
                        b'u' => {
                            let h = self.hex4()?;
                            if h < 0x80 {
                                out.push(h as u8);
                            } else {
                                // encode as utf-8 bytes (sufficient for BMP)
                                let s = char::from_u32(h).ok_or("invalid unicode codepoint")?;
                                for b in s.to_string().as_bytes() {
                                    out.push(*b);
                                }
                            }
                        }
                        c => return Err(format!("bad escape: \\{}", c as char)),
                    }
                    self.i += 1;
                }
                c => {
                    out.push(c);
                    self.i += 1;
                }
            }
        }
    }

    fn hex4(&mut self) -> Result<u32, String> {
        let mut v: u32 = 0;
        for _ in 0..4 {
            let c = self.peek().ok_or("short \\u escape")?;
            self.i += 1;
            v = v * 16
                + match c {
                    b'0'..=b'9' => (c - b'0') as u32,
                    b'a'..=b'f' => (c - b'a' + 10) as u32,
                    b'A'..=b'F' => (c - b'A' + 10) as u32,
                    _ => return Err(format!("bad hex digit: {}", c as char)),
                };
        }
        Ok(v)
    }

    fn num(&mut self) -> Result<V, String> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        while self.peek().map_or(false, |c| c.is_ascii_digit()) {
            self.i += 1;
        }
        if self.peek() == Some(b'.') {
            self.i += 1;
            while self.peek().map_or(false, |c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            self.i += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.i += 1;
            }
            while self.peek().map_or(false, |c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        if self.i == start {
            return Err("expected a number".into());
        }
        let s = std::str::from_utf8(&self.b[start..self.i]).unwrap();
        let n: f64 = s.parse().map_err(|e| format!("bad number '{s}': {e}"))?;
        Ok(V::Num(n))
    }

    fn literal(&mut self, tok: &[u8], v: V) -> Result<V, String> {
        for &c in tok {
            self.eat(c)?;
        }
        Ok(v)
    }
}

fn parse_json(s: &str) -> Result<V, String> {
    let mut p = Jp::new(s.as_bytes());
    let v = p.value()?;
    p.ws();
    if p.i < p.b.len() {
        return Err(format!("trailing garbage at pos {}", p.i));
    }
    Ok(v)
}

// ---------------------------------------------------------------------------
// Helpers for extracting the grammar JSON into typed structs
// ---------------------------------------------------------------------------

type E = String;

fn obj<'a>(v: &'a V, ctx: &str) -> Result<&'a BTreeMap<String, V>, E> {
    match v {
        V::Obj(m) => Ok(m),
        _ => Err(format!("{ctx}: expected object")),
    }
}

fn str_<'a>(v: &'a V, ctx: &str) -> Result<&'a str, E> {
    match v {
        V::Str(s) => Ok(s),
        _ => Err(format!("{ctx}: expected string")),
    }
}

fn strmap(v: &V, ctx: &str) -> Result<BTreeMap<String, String>, E> {
    let m = obj(v, ctx)?;
    let mut out = BTreeMap::new();
    for (k, v) in m {
        out.insert(k.clone(), str_(v, &format!("{ctx}.{k}"))?.to_string());
    }
    Ok(out)
}

fn literalmap(v: &V, ctx: &str) -> Result<BTreeMap<String, V>, E> {
    let m = obj(v, ctx)?;
    Ok(m.clone())
}

// ---------------------------------------------------------------------------
// Grammar (loaded once at startup)
// ---------------------------------------------------------------------------

struct Grammar {
    // Symbol strings ordered longest-first.
    syms: Vec<(String, String)>,
    keywords: BTreeMap<String, String>,
    literals: BTreeMap<String, V>,
    escapes: BTreeMap<char, String>,
    line_comment: String,
    block_comment: String,
}

impl Grammar {
    fn from_value(v: &V) -> Result<Self, E> {
        let root = obj(v, "grammar")?;
        let syms_raw = obj(root.get("symbols").ok_or_else(|| "symbols".to_string())?, "symbols")?;
        let mut syms: Vec<(String, String)> = syms_raw
            .iter()
            .map(|(k, v)| Ok((k.clone(), str_(v, &format!("symbols.{k}"))?.to_string())))
            .collect::<Result<Vec<_>, E>>()?;
        syms.sort_by(|a, b| b.0.len().cmp(&a.0.len()));
        let keywords =
            strmap(root.get("keywords").ok_or_else(|| "keywords".to_string())?, "keywords")?;
        let literals = literalmap(
            root.get("literals").ok_or_else(|| "literals".to_string())?,
            "literals",
        )?;
        let escapes_raw =
            obj(root.get("escapes").ok_or_else(|| "escapes".to_string())?, "escapes")?;
        let mut escapes = BTreeMap::new();
        for (k, v) in escapes_raw {
            let ch = k.chars().next().ok_or_else(|| "empty escape key".to_string())?;
            escapes.insert(ch, str_(v, &format!("escapes.{k}"))?.to_string());
        }
        let line_comment = str_(
            root.get("line_comment")
                .ok_or_else(|| "line_comment".to_string())?,
            "line_comment",
        )?
        .to_string();
        let block_comment = str_(
            root.get("block_comment")
                .ok_or_else(|| "block_comment".to_string())?,
            "block_comment",
        )?
        .to_string();
        Ok(Grammar {
            syms,
            keywords,
            literals,
            escapes,
            line_comment,
            block_comment,
        })
    }
}

// ---------------------------------------------------------------------------
// Lexer error
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
enum ErrKind {
    NumberUnderscore,
    UnexpectedCharacter,
    UnterminatedBlockComment,
}

impl ErrKind {
    fn tag(&self) -> &'static str {
        match self {
            ErrKind::NumberUnderscore => "number_underscore",
            ErrKind::UnexpectedCharacter => "unexpected_character",
            ErrKind::UnterminatedBlockComment => "unterminated_block_comment",
        }
    }
}

impl fmt::Display for ErrKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.tag())
    }
}

#[derive(Debug)]
struct LexErr {
    kind: ErrKind,
    line: usize,
    fragment: String,
}

// ---------------------------------------------------------------------------
// Lexer core -- mirrors src/core/lexer.py exactly
// ---------------------------------------------------------------------------

fn unescape(raw: &str, g: &Grammar) -> String {
    let cs: Vec<char> = raw.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < cs.len() {
        if cs[i] == '\\' && i + 1 < cs.len() {
            let nxt = cs[i + 1];
            match g.escapes.get(&nxt) {
                Some(s) => out.push_str(s),
                None => {
                    out.push('\\');
                    out.push(nxt);
                }
            }
            i += 2;
        } else {
            out.push(cs[i]);
            i += 1;
        }
    }
    out
}

fn lstrip(s: &str) -> &str {
    s.trim_start_matches([' ', '\t'])
}

fn read_token<'a>(
    rest: &'a str,
    line: usize,
    g: &Grammar,
    tokens: &mut Vec<(String, V, usize)>,
) -> Result<&'a str, LexErr> {
    // 1. TEXT -- single-quoted literal
    if rest.starts_with('\'') {
        let bs = rest.as_bytes();
        let mut i: usize = 1;
        while i < bs.len() {
            if bs[i] == b'\\' && i + 1 < bs.len() {
                i += 2;
            } else if bs[i] == b'\'' {
                let inner = &rest[1..i];
                let value = unescape(inner, g);
                tokens.push((String::from("TEXT"), V::Str(value), line));
                return Ok(lstrip(&rest[i + 1..]));
            } else {
                i += 1;
            }
        }
    }

    // 2. NUMBER -- digits, optional fraction
    {
        let bs = rest.as_bytes();
        let mut i: usize = 0;
        while i < bs.len() && bs[i].is_ascii_digit() {
            i += 1;
        }
        if i > 0 {
            // fraction?
            if i < bs.len() && bs[i] == b'.' {
                let mut j = i + 1;
                if j < bs.len() && bs[j].is_ascii_digit() {
                    while j < bs.len() && bs[j].is_ascii_digit() {
                        j += 1;
                    }
                    i = j;
                }
            }
            let after = &rest[i..];
            if after.starts_with('_') && !(after.len() >= 2 && after.as_bytes()[1] == b'_') {
                return Err(LexErr {
                    kind: ErrKind::NumberUnderscore,
                    line,
                    fragment: rest.to_string(),
                });
            }
            tokens.push((String::from("NUMBER"), V::Str(rest[..i].into()), line));
            return Ok(lstrip(after));
        }
    }

    // 3. SYMBOLS -- longest-first, checked before identifiers
    for (sym, ty) in &g.syms {
        if rest.starts_with(sym.as_str()) {
            tokens.push((ty.clone(), V::Str(sym.clone()), line));
            return Ok(lstrip(&rest[sym.len()..]));
        }
    }

    // 4. IDENTIFIER -- [a-zA-Z_][a-zA-Z0-9_]* (but no trailing __)
    {
        let bs = rest.as_bytes();
        if bs[0].is_ascii_alphabetic() || bs[0] == b'_' {
            let mut i: usize = 1;
            while i < bs.len() {
                let c = bs[i];
                if c.is_ascii_alphanumeric() {
                    i += 1;
                } else if c == b'_' && i + 1 < bs.len() && bs[i + 1] == b'_' {
                    break; // __  → reserved range separator, stop here
                } else if c == b'_' {
                    i += 1; // trailing single underscore
                } else {
                    break;
                }
            }
            let word = &rest[..i];
            let ty = g
                .keywords
                .get(word)
                .cloned()
                .unwrap_or_else(|| String::from("IDENTIFIER"));
            let value = match g.literals.get(word) {
                Some(lv) => lv.clone(),
                None => V::Str(word.to_string()),
            };
            tokens.push((ty, value, line));
            return Ok(lstrip(&rest[i..]));
        }
    }

    // 5. ERROR
    Err(LexErr {
        kind: ErrKind::UnexpectedCharacter,
        line,
        fragment: rest.to_string(),
    })
}

fn lex(source: &str, g: &Grammar) -> Result<Vec<(String, V, usize)>, LexErr> {
    let mut tokens: Vec<(String, V, usize)> = Vec::new();
    let mut indents: Vec<usize> = vec![0];
    let mut in_block = false;
    let mut block_start: usize = 1;

    for (raw_idx, raw) in source.split('\n').enumerate() {
        // split('\n') does not drop trailing "" from "a\n" (last iter gives "")
        let line_no = raw_idx + 1;
        let trimmed = raw.trim();
        if trimmed.is_empty() {
            continue;
        }
        if in_block {
            if trimmed.ends_with(&g.block_comment) {
                in_block = false;
            }
            continue;
        }
        if trimmed.starts_with(&g.block_comment) {
            block_start = line_no;
            in_block = true;
            continue;
        }

        let indent = raw.len() - raw.trim_start_matches(' ').len();
        if indent > *indents.last().unwrap() {
            indents.push(indent);
            tokens.push((String::from("INDENT"), V::Null, line_no));
        }
        while indent < *indents.last().unwrap() {
            indents.pop();
            tokens.push((String::from("DEDENT"), V::Null, line_no));
        }

        let mut rest = trimmed;
        while !rest.is_empty() {
            if rest.starts_with(&g.line_comment) {
                break;
            }
            rest = read_token(rest, line_no, g, &mut tokens)?;
        }

        tokens.push((String::from("NEWLINE"), V::Null, line_no));
    }

    while indents.len() > 1 {
        indents.pop();
        let last_line = tokens.last().map(|t| t.2).unwrap_or(1);
        tokens.push((String::from("DEDENT"), V::Null, last_line));
    }

    if in_block {
        return Err(LexErr {
            kind: ErrKind::UnterminatedBlockComment,
            line: block_start,
            fragment: String::new(),
        });
    }

    Ok(tokens)
}

// ---------------------------------------------------------------------------
// JSON serialisation (tokens / errors on stdout)
// ---------------------------------------------------------------------------

fn esc_json(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                use std::fmt::Write as _;
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn json_value(out: &mut String, v: &V) {
    match v {
        V::Null => out.push_str("null"),
        V::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        V::Num(n) => {
            // round-trip: Rust f64 to_string gives "3.14" for 3.14
            use std::fmt::Write as _;
            let _ = write!(out, "{n}");
        }
        V::Str(s) => esc_json(out, s),
        V::Arr(_) | V::Obj(_) => unreachable!("unexpected nested structure in token value"),
    }
}

fn emit_tokens(out: &mut String, tokens: &[(String, V, usize)]) {
    out.push_str("{\"tokens\":[");
    for (i, (t, v, l)) in tokens.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('[');
        esc_json(out, t);
        out.push(',');
        json_value(out, v);
        out.push(',');
        use std::fmt::Write as _;
        let _ = write!(out, "{l}");
        out.push(']');
    }
    out.push_str("]}\n");
}

fn emit_err(out: &mut String, e: &LexErr) {
    out.push_str("{\"error\":{\"kind\":\"");
    out.push_str(e.kind.tag());
    out.push_str("\",\"line\":");
    use std::fmt::Write as _;
    let _ = write!(out, "{}", e.line);
    out.push_str(",\"fragment\":");
    esc_json(out, &e.fragment);
    out.push_str("}}\n");
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

fn run_once_with_grammar(g: &Grammar, source: &str) -> String {
    let mut out = String::new();
    match lex(source, g) {
        Ok(tokens) => emit_tokens(&mut out, &tokens),
        Err(e) => emit_err(&mut out, &e),
    }
    out
}

fn run_serve(g: &Grammar) {
    use std::io::{BufRead, BufReader, BufWriter, Write};
    let stdin = BufReader::new(io::stdin());
    let mut stdout = BufWriter::new(io::stdout());
    for line in stdin.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        // Each request is one JSON document on one line: {"source": "..."}
        let req = match parse_json(&line) {
            Ok(v) => v,
            Err(_) => break,
        };
        let source = match req {
            V::Obj(ref m) => match m.get("source") {
                Some(V::Str(s)) => s.clone(),
                _ => break,
            },
            _ => break,
        };
        let mut out = run_once_with_grammar(g, &source);
        if !out.ends_with('\n') {
            out.push('\n');
        }
        let _ = stdout.write_all(out.as_bytes());
        let _ = stdout.flush();
    }
}

fn main() {
    // `--serve` keeps one long-lived process: read newline-delimited
    // {"source": ...} requests, answer with one JSON result line each.
    // Grammar path is positional when present (argv[2] if --serve, argv[1]
    // otherwise), falling back to LYNX_LEXER_GRAMMAR then the repo default.
    let (serve, grammar_path) = {
        let args: Vec<String> = env::args().skip(1).collect();
        let default_grammar =
            env::var("LYNX_LEXER_GRAMMAR").unwrap_or_else(|_| "src/core/grammar.json".into());
        match args.first().map(|s| s.as_str()) {
            Some("--serve") => (
                true,
                args.get(1)
                    .cloned()
                    .unwrap_or(default_grammar),
            ),
            Some(p) => (false, p.to_string()),
            None => (false, default_grammar),
        }
    };

    let grammar_source = match fs::read_to_string(&grammar_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("lynx-lexer: cannot read grammar {grammar_path}: {e}");
            process::exit(4);
        }
    };

    let grammar_v = match parse_json(&grammar_source) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("lynx-lexer: bad grammar JSON: {e}");
            process::exit(3);
        }
    };

    let g = match Grammar::from_value(&grammar_v) {
        Ok(g) => g,
        Err(e) => {
            eprintln!("lynx-lexer: invalid grammar structure: {e}");
            process::exit(4);
        }
    };

    if serve {
        run_serve(&g);
        return;
    }

    let mut source = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut source) {
        eprintln!("lynx-lexer: stdin read error: {e}");
        process::exit(4);
    }

    print!("{}", run_once_with_grammar(&g, &source));
}