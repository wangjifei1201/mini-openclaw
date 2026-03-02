---
name: docx
description: "当用户想要创建、读取、编辑或操作 Word 文档（.docx 文件）时使用此技能。触发条件包括：提及\"Word 文档\"、\"word document\"、\".docx\"，或请求生成带有目录、标题、页码或信头等格式的专业文档。同时适用于从 .docx 文件中提取或重组内容、插入或替换文档中的图片、在 Word 文件中执行查找和替换、处理修订跟踪或批注，或将内容转换为精美的 Word 文档。如果用户要求以 Word 或 .docx 文件形式生成\"报告\"、\"备忘录\"、\"信件\"、\"模板\"或类似交付物，请使用此技能。请勿用于 PDF、电子表格、Google Docs 或与文档生成无关的一般编码任务。"
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX 创建、编辑和分析

## 概述

.docx 文件是一个包含 XML 文件的 ZIP 压缩包。

## 快速参考

| 任务 | 方法 |
|------|------|
| 读取/分析内容 | `pandoc` 或解压以获取原始 XML |
| 创建新文档 | 使用 `docx-js` - 参见下方的创建新文档 |
| 编辑现有文档 | 解压 → 编辑 XML → 重新打包 - 参见下方的编辑现有文档 |

### 将 .doc 转换为 .docx

必须先转换旧版 `.doc` 文件才能编辑：

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### 读取内容

```bash
# 提取带有修订跟踪的文本
pandoc --track-changes=all document.docx -o output.md

# 访问原始 XML
python scripts/office/unpack.py document.docx unpacked/
```

### 转换为图片

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### 接受修订跟踪

要生成接受所有修订跟踪的干净文档（需要 LibreOffice）：

```bash
python scripts/accept_changes.py input.docx output.docx
```

---

## 创建新文档

使用 JavaScript 生成 .docx 文件，然后进行验证。安装：`npm install -g docx`

### 设置
```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### 验证
创建文件后，进行验证。如果验证失败，解压、修复 XML 并重新打包。
```bash
python scripts/office/validate.py doc.docx
```

### 页面尺寸

```javascript
// 重要：docx-js 默认使用 A4，不是美标信纸
// 始终显式设置页面尺寸以获得一致的结果
sections: [{
  properties: {
    page: {
      size: {
        width: 12240,   // DXA 单位的 8.5 英寸
        height: 15840   // DXA 单位的 11 英寸
      },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 英寸边距
    }
  },
  children: [/* content */]
}]
```

**常用页面尺寸（DXA 单位，1440 DXA = 1 英寸）：**

| 纸张 | 宽度 | 高度 | 内容宽度（1 英寸边距） |
|-------|-------|--------|---------------------------|
| 美标信纸 | 12,240 | 15,840 | 9,360 |
| A4（默认） | 11,906 | 16,838 | 9,026 |

**横向：** docx-js 内部会交换宽/高，所以传入纵向尺寸让它自行处理交换：
```javascript
size: {
  width: 12240,   // 将短边作为宽度传入
  height: 15840,  // 将长边作为高度传入
  orientation: PageOrientation.LANDSCAPE  // docx-js 会在 XML 中交换它们
},
// 内容宽度 = 15840 - 左边距 - 右边距（使用长边）
```

### 样式（覆盖内置标题）

使用 Arial 作为默认字体（通用支持）。标题保持黑色以确保可读性。

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } }, // 默认 12pt
    paragraphStyles: [
      // 重要：使用精确的 ID 来覆盖内置样式
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } }, // 目录需要 outlineLevel
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Title")] }),
    ]
  }]
});
```

### 列表（切勿使用 Unicode 项目符号）

```javascript
// 错误 - 永远不要手动插入项目符号字符
new Paragraph({ children: [new TextRun("• Item")] })  // 错误
new Paragraph({ children: [new TextRun("\u2022 Item")] })  // 错误

// 正确 - 使用编号配置和 LevelFormat.BULLET
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ]
  }]
});

// 注意：每个引用创建独立的编号
// 相同引用 = 继续（1,2,3 然后 4,5,6）
// 不同引用 = 重新开始（1,2,3 然后 1,2,3）
```

### 表格

**重要：表格需要双重宽度** - 在表格上设置 `columnWidths`，在每个单元格上设置 `width`。缺少任何一个，表格在某些平台上都会渲染不正确。

```javascript
// 重要：始终设置表格宽度以确保一致渲染
// 重要：使用 ShadingType.CLEAR（不是 SOLID）以防止黑色背景
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA }, // 始终使用 DXA（百分比在 Google Docs 中会出问题）
  columnWidths: [4680, 4680], // 必须等于表格宽度（DXA：1440 = 1 英寸）
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA }, // 也要在每个单元格上设置
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR }, // CLEAR 不是 SOLID
          margins: { top: 80, bottom: 80, left: 120, right: 120 }, // 单元格内边距（内部，不计入宽度）
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
})
```

**表格宽度计算：**

始终使用 `WidthType.DXA` — `WidthType.PERCENTAGE` 在 Google Docs 中会出问题。

```javascript
// 表格宽度 = columnWidths 的总和 = 内容宽度
// 美标信纸 1 英寸边距：12240 - 2880 = 9360 DXA
width: { size: 9360, type: WidthType.DXA },
columnWidths: [7000, 2360]  // 必须等于表格宽度
```

**宽度规则：**
- **始终使用 `WidthType.DXA`** — 不要使用 `WidthType.PERCENTAGE`（与 Google Docs 不兼容）
- 表格宽度必须等于 `columnWidths` 的总和
- 单元格 `width` 必须对应 `columnWidth`
- 单元格 `margins` 是内部内边距 - 它们减少内容区域，而不是增加单元格宽度
- 对于全宽表格：使用内容宽度（页面宽度减去左右边距）

### 图片

```javascript
// 重要：type 参数是必需的
new Paragraph({
  children: [new ImageRun({
    type: "png", // 必需：png、jpg、jpeg、gif、bmp、svg
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" } // 三个都是必需的
  })]
})
```

### 分页符

```javascript
// 重要：PageBreak 必须在 Paragraph 内部
new Paragraph({ children: [new PageBreak()] })

// 或使用 pageBreakBefore
new Paragraph({ pageBreakBefore: true, children: [new TextRun("New page")] })
```

### 目录

```javascript
// 重要：标题必须只使用 HeadingLevel - 不要使用自定义样式
new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" })
```

### 页眉/页脚

```javascript
sections: [{
  properties: {
    page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } // 1440 = 1 英寸
  },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("Header")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("Page "), new TextRun({ children: [PageNumber.CURRENT] })]
    })] })
  },
  children: [/* content */]
}]
```

### docx-js 的关键规则

- **显式设置页面尺寸** - docx-js 默认使用 A4；美标文档使用美标信纸（12240 x 15840 DXA）
- **横向：传入纵向尺寸** - docx-js 内部交换宽/高；将短边作为 `width`，长边作为 `height`，并设置 `orientation: PageOrientation.LANDSCAPE`
- **不要使用 `\n`** - 使用单独的 Paragraph 元素
- **不要使用 Unicode 项目符号** - 使用 `LevelFormat.BULLET` 和编号配置
- **PageBreak 必须在 Paragraph 中** - 单独使用会创建无效 XML
- **ImageRun 需要 `type`** - 始终指定 png/jpg 等
- **始终使用 DXA 设置表格 `width`** - 不要使用 `WidthType.PERCENTAGE`（在 Google Docs 中会出问题）
- **表格需要双重宽度** - `columnWidths` 数组和单元格 `width`，两者必须匹配
- **表格宽度 = columnWidths 的总和** - 对于 DXA，确保它们完全相加
- **始终添加单元格边距** - 使用 `margins: { top: 80, bottom: 80, left: 120, right: 120 }` 以获得可读的内边距
- **使用 `ShadingType.CLEAR`** - 表格底纹不要使用 SOLID
- **目录只需要 HeadingLevel** - 标题段落不要使用自定义样式
- **覆盖内置样式** - 使用精确的 ID："Heading1"、"Heading2" 等
- **包含 `outlineLevel`** - 目录需要（H1 为 0，H2 为 1，等等）

---

## 编辑现有文档

**按顺序执行所有 3 个步骤。**

### 步骤 1：解压
```bash
python scripts/office/unpack.py document.docx unpacked/
```
解压 XML，美化打印，合并相邻的运行，并将智能引号转换为 XML 实体（`&#x201C;` 等）以便在编辑中保留。使用 `--merge-runs false` 跳过运行合并。

### 步骤 2：编辑 XML

编辑 `unpacked/word/` 中的文件。参见下方的 XML 参考以获取模式。

**除非用户明确要求使用不同的名称，否则使用 "Claude" 作为修订跟踪和批注的作者。**

**直接使用编辑工具进行字符串替换。不要编写 Python 脚本。** 脚本会引入不必要的复杂性。编辑工具确切显示了要替换的内容。

**重要：新内容使用智能引号。** 添加包含撇号或引号的文本时，使用 XML 实体来生成智能引号：
```xml
<!-- 使用这些实体实现专业排版 -->
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```
| 实体 | 字符 |
|--------|-----------|
| `&#x2018;` | '（左单引号） |
| `&#x2019;` | '（右单引号 / 撇号） |
| `&#x201C;` | "（左双引号） |
| `&#x201D;` | "（右双引号） |

**添加批注：** 使用 `comment.py` 处理跨多个 XML 文件的样板代码（文本必须是预转义的 XML）：
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # 回复批注 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"  # 自定义作者名称
```
然后在 document.xml 中添加标记（参见 XML 参考中的批注部分）。

### 步骤 3：打包
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
使用自动修复进行验证，压缩 XML，并创建 DOCX。使用 `--validate false` 跳过。

**自动修复将修复：**
- `durableId` >= 0x7FFFFFFF（重新生成有效 ID）
- 带有空白字符的 `<w:t>` 缺少 `xml:space="preserve"`

**自动修复不会修复：**
- 格式错误的 XML、无效的元素嵌套、缺少关系、模式违规

### 常见陷阱

- **替换整个 `<w:r>` 元素**：添加修订跟踪时，将整个 `<w:r>...</w:r>` 块替换为 `<w:del>...<w:ins>...` 作为兄弟元素。不要在运行内部注入修订跟踪标签。
- **保留 `<w:rPr>` 格式**：将原始运行的 `<w:rPr>` 块复制到修订跟踪运行中以保持粗体、字体大小等。

---

## XML 参考

### 模式合规性

- **`<w:pPr>` 中的元素顺序**：`<w:pStyle>`、`<w:numPr>`、`<w:spacing>`、`<w:ind>`、`<w:jc>`、`<w:rPr>` 最后
- **空白字符**：在带有前导/尾随空格的 `<w:t>` 上添加 `xml:space="preserve"`
- **RSID**：必须是 8 位十六进制（例如，`00AB1234`）

### 修订跟踪

**插入：**
```xml
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

**删除：**
```xml
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**在 `<w:del>` 内部**：使用 `<w:delText>` 代替 `<w:t>`，使用 `<w:delInstrText>` 代替 `<w:instrText>`。

**最小化编辑** - 只标记更改的内容：
```xml
<!-- 将 "30 days" 更改为 "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

**删除整个段落/列表项** - 从段落中删除所有内容时，也要将段落标记标记为已删除，以便它与下一段落合并。在 `<w:pPr><w:rPr>` 内添加 `<w:del/>`：
```xml
<w:p>
  <w:pPr>
    <w:numPr>...</w:numPr>  <!-- 如果存在列表编号 -->
    <w:rPr>
      <w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```
如果没有 `<w:pPr><w:rPr>` 中的 `<w:del/>`，接受更改后会留下空段落/列表项。

**拒绝另一位作者的插入** - 在其插入内部嵌套删除：
```xml
<w:ins w:author="Jane" w:id="5">
  <w:del w:author="Claude" w:id="10">
    <w:r><w:delText>their inserted text</w:delText></w:r>
  </w:del>
</w:ins>
```

**恢复另一位作者的删除** - 在其删除后添加插入（不要修改他们的删除）：
```xml
<w:del w:author="Jane" w:id="5">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
<w:ins w:author="Claude" w:id="10">
  <w:r><w:t>deleted text</w:t></w:r>
</w:ins>
```

### 批注

运行 `comment.py` 后（参见步骤 2），在 document.xml 中添加标记。对于回复，使用 `--parent` 标志并在父级内部嵌套标记。

**重要：`<w:commentRangeStart>` 和 `<w:commentRangeEnd>` 是 `<w:r>` 的兄弟元素，绝不在 `<w:r>` 内部。**

```xml
<!-- 批注标记是 w:p 的直接子元素，绝不在 w:r 内部 -->
<w:commentRangeStart w:id="0"/>
<w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted</w:delText></w:r>
</w:del>
<w:r><w:t> more text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>

<!-- 嵌套回复 1 的批注 0 -->
<w:commentRangeStart w:id="0"/>
  <w:commentRangeStart w:id="1"/>
  <w:r><w:t>text</w:t></w:r>
  <w:commentRangeEnd w:id="1"/>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>
```

### 图片

1. 将图片文件添加到 `word/media/`
2. 将关系添加到 `word/_rels/document.xml.rels`：
```xml
<Relationship Id="rId5" Type=".../image" Target="media/image1.png"/>
```
3. 将内容类型添加到 `[Content_Types].xml`：
```xml
<Default Extension="png" ContentType="image/png"/>
```
4. 在 document.xml 中引用：
```xml
<w:drawing>
  <wp:inline>
    <wp:extent cx="914400" cy="914400"/>  <!-- EMU：914400 = 1 英寸 -->
    <a:graphic>
      <a:graphicData uri=".../picture">
        <pic:pic>
          <pic:blipFill><a:blip r:embed="rId5"/></pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

---

## 依赖项

- **pandoc**：文本提取
- **docx**：`npm install -g docx`（新文档）
- **LibreOffice**：PDF 转换（通过 `scripts/office/soffice.py` 自动配置沙盒环境）
- **Poppler**：图片转换 `pdftoppm`
