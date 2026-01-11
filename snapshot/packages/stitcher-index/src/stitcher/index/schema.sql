-- File System Tracking
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    last_mtime REAL NOT NULL,
    last_size INTEGER NOT NULL,
    -- 0: Dirty (needs re-indexing), 1: Indexed
    indexing_status INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);

-- Symbol Definitions
CREATE TABLE IF NOT EXISTS symbols (
    -- Stitcher Uniform Resource Identifier (SURI) -> py://<rel_path>#<fragment>
    id TEXT PRIMARY KEY,
    file_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    
    -- The fully qualified name, unique within the project.
    -- e.g., my_pkg.utils.helper
    canonical_fqn TEXT,
    
    -- Relative logical path within the file, e.g., MyClass.my_method
    logical_path TEXT,
    kind TEXT NOT NULL,

    -- ALIAS-SPECIFIC FIELDS --
    -- The logical FQN this alias points to, extracted directly by the parser.
    -- e.g., "my_pkg.utils.helper" for "from my_pkg.utils import helper"
    alias_target_fqn TEXT,
    
    -- The resolved SURI of the target symbol (FK to symbols.id).
    -- This is populated by the Linker phase. Can be NULL if unresolved.
    alias_target_id TEXT,

    -- Location in source file
    lineno INTEGER NOT NULL,
    col_offset INTEGER NOT NULL,
    end_lineno INTEGER NOT NULL,
    end_col_offset INTEGER NOT NULL,
    
    -- Structural hash of the symbol's signature
    signature_hash TEXT,
    
    -- The raw text signature of the symbol (e.g. "def foo(a: int) -> str:")
    signature_text TEXT,
    
    -- The SHA256 hash of the docstring content
    docstring_hash TEXT,
    
    -- The raw, unprocessed docstring content
    docstring_content TEXT,

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (alias_target_id) REFERENCES symbols(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_canonical_fqn ON symbols(canonical_fqn);


-- Symbol References
CREATE TABLE IF NOT EXISTS 'references' (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL,

    -- The logical FQN of the target, extracted by the parser.
    -- e.g., "os.path.join"
    target_fqn TEXT NOT NULL,
    
    -- The resolved SURI of the target symbol (FK to symbols.id).
    -- This is populated by the Linker phase. Can be NULL if unresolved.
    target_id TEXT,

    kind TEXT NOT NULL, -- e.g., 'import', 'call', 'annotation'
    
    -- Location of the reference in the source file
    lineno INTEGER NOT NULL,
    col_offset INTEGER NOT NULL,
    end_lineno INTEGER NOT NULL,
    end_col_offset INTEGER NOT NULL,

    FOREIGN KEY (source_file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES symbols(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_references_source_file_id ON 'references'(source_file_id);
CREATE INDEX IF NOT EXISTS idx_references_target_id ON 'references'(target_id);