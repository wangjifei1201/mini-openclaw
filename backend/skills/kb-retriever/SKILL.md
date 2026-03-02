---
name: kb-retriever
description: 面向本地知识库目录的检索和问答助手。核心流程：(1)调用 RAG 检索 API 获取相关文档范围 (2)严格在 API 返回的文档范围内进行二次检索 (3)按文件类型使用对应工具进行精细化检索。用户问题涉及"从知识库目录回答问题/检索信息/查资料"时使用。
dependency:
  python:
    - pdf2image>=1.17.0
    - Pillow>=12.1.1
    - pypdf>=6.7.0
    - pdfplumber>=0.11.9
    - pandas>=3.0.0
    - openpyxl>=3.1.5
    - xlrd>=2.0.2
    - requests>=2.31.0
---

# 本地知识库检索 Skill（kb-retriever）

## 前置准备
- 依赖安装：使用阿里云镜像源安装依赖包（推荐）
  ```bash
  pip install -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com pdf2image>=1.17.0 Pillow>=12.1.1 pypdf>=6.7.0 pdfplumber>=0.11.9 pandas>=3.0.0 openpyxl>=3.1.5 xlrd>=2.0.2 requests>=2.31.0
  ```

## 核心原则：API 优先，范围限定

### ⚠️ 强制性工作流程

**当用户问题需要知识检索时，必须严格按照以下顺序执行：**

1. **第一步（强制）**：调用 RAG 检索 API 接口
   - 使用 `fetch_url` 或 `python_repl` 调用 `POST /api/v1/retrieval/search`
   - 获取相关文档片段和元数据
   
2. **第二步（强制）**：解析 API 响应，提取文档范围
   - 从 `documents` 字段提取所有文档的 `file_path` 和 `file_name`
   - 这些文档构成**唯一合法的检索范围**
   
3. **第三步（强制）**：严格在限定范围内执行二次检索
   - **禁止**检索 API 返回范围之外的任何文件
   - **禁止**使用 Glob 或其他工具探索未授权的目录
   - 只能在 API 返回的文档列表内使用 grep、Read、pdfplumber、pandas 等工具

4. **第四步**：参考 API 返回的片段内容
   - `contents` 字段中的片段可作为回答的直接参考
   - 如需更详细内容，在限定范围内读取对应文件的局部区域

### 范围限定规则

```
合法检索范围 = API 响应中的 documents[].file_path 列表

允许的操作：
✅ 读取 API 返回文档的内容
✅ 在 API 返回的文档内使用 grep 检索
✅ 使用 pdfplumber/pandas 处理 API 返回的 PDF/Excel
✅ 参考 API 返回的 contents 片段

禁止的操作：
❌ 检索未在 documents 列表中出现的文件
❌ 使用 Glob 探索知识库目录结构
❌ 读取 data_structure.md 等索引文件（除非 API 返回了它）
❌ 递归遍历子目录
❌ 访问 API 返回路径之外的任何文件
```

## RAG 检索 API 接口说明

### 接口信息

- **Base URL**: `http://{host}:{port}/api/v1`
- **接口路径**: `POST /retrieval/search`
- **认证**: 无需认证（匿名开放）

### 请求参数

```json
{
  "query": "用户问题",
  "top_k": 10,  // 可选，默认 10，范围 1-50
  "doc_scope": null  // 可选，限定文档 ID 列表
}
```

### 响应结构

```json
{
  "query": "原始查询问题",
  "total_chunks": 5,
  "contents": [
    {
      "chunk_id": "chunk_001",
      "content": "片段文本内容",
      "doc_id": "doc_abc123",
      "doc_name": "员工手册.pdf",
      "chapter": "第三章 考勤管理",
      "section": "3.2 请假制度",
      "page": 15,
      "score": 0.92
    }
  ],
  "documents": [
    {
      "doc_id": "doc_abc123",
      "file_name": "员工手册.pdf",
      "file_path": "/documents/hr/员工手册.pdf",
      "file_format": "pdf",
      "department": "人力资源部",
      "category": "制度文件"
    }
  ]
}
```

### 调用示例（Python）

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/retrieval/search",
    json={
        "query": "员工请假流程是什么？",
        "top_k": 10
    }
)
result = response.json()

# 提取限定范围
allowed_paths = [doc["file_path"] for doc in result["documents"]]
print(f"限定检索范围：{allowed_paths}")

# 提取参考片段
for chunk in result["contents"]:
    print(f"[{chunk['doc_name']}] P{chunk['page']}: {chunk['content'][:100]}...")
```

## 知识库目录说明（仅当 API 返回索引文件时使用）

- 知识库存放在一个根目录下，包含多种文件类型（如 `.md`/`.txt`、`.pdf`、`.xlsx` 等）
- **注意**：只有在 API 响应中包含 `data_structure.md` 或类似索引文件时，才能读取这些文件
- 默认知识库根目录：`/Users/wangjifei/Desktop/knowledge/`
- 如果用户指定了其他路径，以用户指定为准

### 定位 `knowledge` 根目录

- 根目录优先听用户：如果用户给了路径（如 `./docs`、`./knowledge-personal`），直接用用户提供的路径
- 默认根目录：否则约定根目录为当前项目下的 `knowledge/`
- **重要**：目录存在性检查仅在 API 返回的文档路径需要使用这些路径时才进行

## 关键原则：先学习，再处理

**遇到 PDF 或 Excel 文件时的强制检查清单**：

- [ ] ✅ 已完成 RAG API 调用并获取文档范围
- [ ] ✅ 确认目标文件在 API 返回的 documents 列表中
- [ ] ✅ 已读取对应的 references 文档学习处理方法
- [ ] ✅ 已理解推荐的工具和命令
- [ ] ✅ 已将文件处理（提取/转换）完成
- [ ] ⏭️ 现在可以开始检索

**禁止行为**：
- ❌ 未调用 RAG API 就直接开始检索
- ❌ 检索 API 返回范围之外的文件
- ❌ 在未读取 pdf_reading.md 的情况下直接尝试处理 PDF
- ❌ 在未读取 excel_reading.md 的情况下直接尝试处理 Excel
- ❌ 跳过文件处理步骤，直接对原始 PDF/Excel 进行检索

## 总体流程

### 阶段 1：API 检索（强制第一步）

1. **理解用户需求**
   - 读用户问题，提取：
     - 主题/领域关键词（如"销售报表""系统架构""接口文档"）
     - 时间或范围限定（如"2023 年 Q1""最近版本"）
     - 需要的输出类型（解释、摘要、具体字段数值等）

2. **调用 RAG 检索 API**
   - 使用 `python_repl` 或 `fetch_url` 调用接口
   - 默认参数：`top_k=10`
   - 如果用户指定了知识库路径，可在后续处理中使用

3. **解析 API 响应**
   - 提取 `documents` 列表 → 构建**合法文件路径集合**
   - 提取 `contents` 列表 → 作为**初步参考内容**
   - 记录每个文档的：
     - `file_path`: 文件完整路径
     - `file_name`: 文件名
     - `file_format`: 文件格式
     - `doc_name`: 文档名称

4. **范围验证**
   - 明确告知用户："已找到 X 个相关文档，将在以下范围内进行详细检索"
   - 列出文档清单（文件名 + 路径）

### 阶段 2：范围内二次检索

5. **学习文件处理方法（遇到 PDF/Excel 时强制执行）**
   - **在处理 PDF 文件前**：
     - **必须先读取** [references/pdf_reading.md](references/pdf_reading.md) 学习提取方法
     - 重点了解：pdftotext 命令、pdfplumber 用法、表格提取方法
   - **在处理 Excel 文件前**：
     - **必须先读取** [references/excel_reading.md](references/excel_reading.md) 学习读取方法
     - **必须先读取** [references/excel_analysis.md](references/excel_analysis.md) 学习分析方法
     - 重点了解：pandas 读取、列筛选、数据过滤

6. **按文件类型执行处理和检索**
   - **严格限制**：只处理 API 返回的 documents 列表中的文件
   - 对每个文件，按照「Markdown/文本」「PDF」「Excel」策略执行
   - 总原则：
     - 优先从相关性分数高的文档开始（参考 contents 中的 score）
     - 每个文件内都渐进式地局部检索，避免一次性加载全内容
     - 若当前文件得不到满意信息，切换到下一个候选文件

7. **迭代检索（最多 5 次）**
   - 在限定范围内应用「多轮迭代检索机制」
   - 每次迭代都必须检查目标文件是否在允许范围内

8. **答案组织与溯源**
   - 汇总多轮检索得到的上下文，综合回答用户问题
   - 溯源信息：
     - 优先标注 API 返回的片段（doc_name + page/chapter）
     - 其次标注二次检索获取的详细内容（文件名 + 位置）
   - 如果答案基于推断或信息不完全：
     - 明确标注假设与不确定性
     - 提示用户可以补充更具体的关键词或范围

## 公共检索原则

### 范围检查机制

**在每次文件操作前必须执行**：

```python
# 伪代码示例
allowed_paths = set(api_response["documents"].file_path)

def check_file_access(file_path):
    if file_path not in allowed_paths:
        raise PermissionError(f"文件 {file_path} 不在 API 返回的检索范围内，禁止访问")
    return True
```

### 关键词选择策略
- 从用户问题提取 3-8 个关键词（含可能的英文缩写、同义词、上位/下位词）
- 可组合词组（如 "销售 报表"、"API 接口 超时"）
- 必要时包含业务词、技术术语、常见缩写（如 "uv"、"pv"、"GMV"）

### grep 检索基本原则
- **始终检查**：目标文件是否在 API 返回的允许列表中
- 指定尽量精准的 include 和 path
- pattern 优先尝试问题中的核心名词、术语，再尝试同义词
- 对于每个命中，只读取匹配附近的局部区域（上下若干行）
- 保存「文件名 + 位置信息 + 文本片段」

### 多轮迭代检索机制（最多 5 次）

1. **迭代控制**
   - 维护「已尝试检索次数」计数，最多 5 次
   - 每次检索后累加计数

2. **每轮迭代流程**
   1. 基于问题生成/更新检索关键词（可包括同义词、扩展词）
   2. 选择尚未充分检索的文件（必须在允许范围内）
   3. **范围检查**：确认文件在 API 返回的 documents 列表中
   4. 执行检索（grep/局部读取/专用 Skill 调用）
   5. 分析获取的上下文片段
   6. 判断是否足够回答问题

3. **终止条件**
   - 找到足够支撑回答的上下文；或
   - 已达到 5 次尝试仍未找到合适信息

4. **信息不足时的处理**
   - 明确告知用户信息缺失或可能不在当前知识库中
   - 提供已找到的最接近信息，并说明不确定性
   - 提示用户可以如何缩小范围（更具体的文件名、关键词、时间范围等）

## 针对不同文件类型的具体策略

### 1. Markdown / 文本类文件（.md, .txt, .log 等）

**前提**：文件必须在 API 返回的 documents 列表中

1. **范围验证**
   - 检查文件路径是否在 `allowed_paths` 中
   - 如不在，跳过该文件

2. **grep 定位与局部读取**
   - 使用 Grep 工具对指定文件，include 限定具体后缀
   - 对于有匹配的文件，使用 Read 仅读取匹配附近的局部区域：
     - 通过行号偏移和 limit 控制读取（例如从匹配行附近往前后各读取几十行）
     - 避免整文件读取

3. **参考 API 片段**
   - 如 API 返回了该文件的 contents，优先参考这些片段
   - 如需更详细内容，再读取文件局部

4. **特殊处理**
   - 如内容仅是目录/标题，根据链接或小节名继续定位深入内容（仍在允许范围内）
   - 应用「多轮迭代检索机制」

### 2. PDF 文件检索策略

**前提**：文件必须在 API 返回的 documents 列表中

**工作流**：

1. **范围验证**
   - 检查文件路径是否在 `allowed_paths` 中
   - 如不在，跳过该文件并告知用户

2. **读取处理方法指南**
   - **必须先读取** [references/pdf_reading.md](references/pdf_reading.md)
   - 重点了解：pdftotext 命令、pdfplumber 用法、表格提取方法、快速决策表

3. **参考 API 返回片段**
   - 如 API 返回了该 PDF 的 contents，先阅读这些片段
   - 记录片段所在的页码（page 字段）

4. **提取文本**
   - 使用 pdf_reading.md 中推荐的工具（优先 pdftotext 或 pdfplumber）
   - **重要**：使用 `pdftotext input.pdf output.txt` 将文本提取到文件
   - 如需提取表格，使用 pdfplumber 的表格提取功能
   - **优化**：如已知目标页码（从 API contents 获取），可只提取特定页面范围

5. **对提取结果执行检索**
   - 使用 grep 对提取的文本进行关键词搜索
   - 对于每个命中，提取命中附近范围的上下文
   - 保存「文件名 + 页码/大致位置 + 文本片段」
   - 应用「多轮迭代检索机制」

### 3. Excel 文件检索策略

**前提**：文件必须在 API 返回的 documents 列表中

**工作流**：

1. **范围验证**
   - 检查文件路径是否在 `allowed_paths` 中
   - 如不在，跳过该文件并告知用户

2. **读取处理方法指南**
   - **必须先读取**：
     - [references/excel_reading.md](references/excel_reading.md) - 学习如何读取工作表
     - [references/excel_analysis.md](references/excel_analysis.md) - 学习如何分析数据
   - 重点了解：pandas 读取方法、列筛选、数据过滤、聚合操作

3. **参考 API 返回片段**
   - 如 API 返回了该 Excel 的 contents，先阅读这些片段
   - 可能包含工作表名、列名等线索

4. **探索结构**
   - 使用 pandas 读取前 10-50 行（使用 `nrows` 参数限制）
   - 重点掌握：列名/字段名、数据类型、关键字段
   - 将列名与用户问题比对，识别潜在关键字段

5. **执行数据检索和分析**
   - 使用学到的 pandas 方法进行过滤和聚合
   - 每次只读取匹配行附近的数据，避免一次性读取整表
   - 如问题包含时间范围，在检索中加入时间过滤
   - 应用「多轮迭代检索机制」

## 与其他工具的协同

### API 调用

- 使用 `python_repl` 执行 requests 调用
- 或使用 `fetch_url`（如支持 POST）
- 处理可能的错误：
  - 422：参数验证失败
  - 500：服务器错误
  - 连接失败：告知用户 API 不可用

### PDF 处理
- **在处理 PDF 前必须先读取** [references/pdf_reading.md](references/pdf_reading.md) 学习处理方法
- 使用 pdfplumber/pypdf 进行文本提取、表格提取、元数据读取
- 优先使用 pdftotext 命令行工具进行快速文本提取

### Excel 处理
- **在处理 Excel 前必须先读取**：
  - [references/excel_reading.md](references/excel_reading.md) - 学习读取方法
  - [references/excel_analysis.md](references/excel_analysis.md) - 学习分析方法
- 使用 pandas 进行数据探索、预览、过滤和分析

### 工具使用原则
- **范围检查优先**：任何文件操作前检查是否在允许列表中
- **Grep**：用于按关键词在指定文件中查找行号与匹配片段
- **Read**：只用于局部读取文件，始终设置合理的 limit（如 200-500 行）
- **对于任何可能很大的文件**：
  - 禁止直接从头读到尾
  - 始终先通过 API 片段定位大致位置后再读

## 回答风格与错误处理

### 回答风格
- 尽量用用户提问的语言（中文/英文）作答
- **先说明检索范围**：
  - "基于 RAG 检索，找到 X 个相关文档：[文档列表]"
  - "将在以下限定范围内进行详细检索..."
- 先给出结论，再给出简要依据
- 如需要，可在后面列出引用的文件和大致位置：
  - 来源：API 检索 - 员工手册.pdf 第 15 页
  - 来源：二次检索 - design/api_gateway.md 第 100 行附近
  - 来源：reports/2023_Q1_sales.xlsx Summary 工作表

### 信息缺失或不确定时
- 明确说明在当前知识库中没有找到完全匹配的信息或只能部分回答
- 不臆造事实
- 提示用户可以如何帮助缩小范围：
  - 提供更精确的关键词或字段名
  - 指定时间/版本范围
  - 确认问题是否在其他知识库中

### API 调用失败处理
- 如 API 不可用，明确告知用户
- 询问用户是否要：
  - 重试 API 调用
  - 使用其他方式（如直接指定文件）
  - 终止任务

## 示例工作流程

### 示例 1：查询员工请假流程

```
用户：员工请假流程是什么？

步骤 1：调用 RAG API
  POST /api/v1/retrieval/search
  {
    "query": "员工请假流程是什么？",
    "top_k": 10
  }

步骤 2：解析响应
  documents: [
    {file_name: "员工手册.pdf", file_path: "/knowledge/hr/员工手册.pdf"},
    {file_name: "考勤管理制度.docx", file_path: "/knowledge/hr/考勤管理制度.docx"}
  ]
  contents: [
    {doc_name: "员工手册.pdf", page: 15, content: "员工请假需提前 3 个工作日...", score: 0.92},
    ...
  ]

步骤 3：告知用户范围
  "已找到 2 个相关文档：
   1. 员工手册.pdf (/knowledge/hr/员工手册.pdf)
   2. 考勤管理制度.docx (/knowledge/hr/考勤管理制度.docx)
   将在以上范围内进行详细检索..."

步骤 4：范围内二次检索
  - 检查文件在允许列表中 ✓
  - 读取 pdf_reading.md 学习 PDF 处理方法
  - 使用 pdftotext 提取员工手册.pdf 文本
  - grep 检索"请假流程"关键词
  - 读取匹配附近的详细内容

步骤 5：综合回答
  "根据检索到的文档，员工请假流程如下：
   1. 提前 3 个工作日提交申请
   2. 填写《请假申请表》
   3. 经部门主管审批后生效
   ...
   
   来源：
   - API 检索：员工手册.pdf 第 15 页
   - 二次检索：考勤管理制度.docx 第 3 章"
```

## 注意事项

- **禁止**第一次就直接调用 Glob 或任何试图探索目录结构的操作
- **必须**先调用 RAG API 获取文档范围
- **严格**在 API 返回的 documents 列表内执行所有文件操作
- 使用本 Skill 查询知识库时，禁止使用网络搜索等其他工具获取知识
- 如 API 返回空结果（total_chunks=0），直接告知用户未找到相关文档，无需执行后续步骤
