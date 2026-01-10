-- Stitcher Index Schema v1.1
-- Dialect: SQLite
-- Mode: WAL (Write-Ahead Logging) enabled

-- ============================================================================
-- 1. Files Table
-- 物理文件状态跟踪。用于增量扫描的快速过滤。
-- ============================================================================
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 仓库根目录相对路径 (e.g., "packages/core/main.py")
    path TEXT UNIQUE NOT NULL,
    
    -- 内容哈希 (SHA256)，用于检测内容变更
    content_hash TEXT NOT NULL,
    
    -- 文件系统元数据，用于第一级快速过滤
    last_mtime REAL NOT NULL,
    last_size INTEGER NOT NULL,
    
    -- 扫描状态标记
    -- 0: Dirty/Pending, 1: Indexed
    indexing_status INTEGER DEFAULT 0
);

-- ============================================================================
-- 2. Symbols Table
-- 语义节点表。存储所有定义 (Definitions) 和 别名 (Aliases/Exports)。
-- ============================================================================
CREATE TABLE IF NOT EXISTS symbols (
    -- 主键：SURI (Stitcher Uniform Resource Identifier)
    id TEXT PRIMARY KEY,
    
    -- 外键：所属文件
    file_id INTEGER NOT NULL,
    
    -- 符号短名，用于模糊搜索和 UI 显示 (e.g., "User", "run")
    name TEXT NOT NULL,
    
    -- 符号全限定名 (逻辑路径)，仅用于展示
    logical_path TEXT,
    
    -- 符号类型 (class, function, variable, alias, module)
    kind TEXT NOT NULL,
    
    -- [核心机制] 别名目标 ID
    alias_target_id TEXT,
    
    -- 源代码位置范围
    lineno INTEGER NOT NULL,
    col_offset INTEGER NOT NULL,
    end_lineno INTEGER NOT NULL,
    end_col_offset INTEGER NOT NULL,
    
    -- (可选) 签名哈希，用于检测 API 变更
    signature_hash TEXT,
    
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_alias_target ON symbols(alias_target_id);

-- ============================================================================
-- 3. References Table
-- 引用边表。存储所有的“使用” (Usages) 和“导入” (Imports)。
-- ============================================================================
CREATE TABLE IF NOT EXISTS "references" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 引用源文件
    source_file_id INTEGER NOT NULL,
    
    -- 引用指向的目标 SURI
    target_id TEXT NOT NULL,
    
    -- 引用类型 (import, call, inheritance, type_hint)
    kind TEXT NOT NULL,
    
    -- 源代码位置范围
    lineno INTEGER NOT NULL,
    col_offset INTEGER NOT NULL,
    end_lineno INTEGER NOT NULL,
    end_col_offset INTEGER NOT NULL,
    
    FOREIGN KEY (source_file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_refs_source_file ON "references"(source_file_id);
CREATE INDEX IF NOT EXISTS idx_refs_target_id ON "references"(target_id);

-- ============================================================================
-- 4. Errors Table
-- 用于记录索引过程中发生的解析错误
-- ============================================================================
CREATE TABLE IF NOT EXISTS indexing_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    error_message TEXT NOT NULL,
    traceback TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);