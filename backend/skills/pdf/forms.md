**重要：您必须按顺序完成这些步骤。不要跳过直接编写代码。**

如果您需要填写 PDF 表单，首先检查 PDF 是否有可填写的表单字段。从此文件的目录运行此脚本：
 `python scripts/check_fillable_fields <file.pdf>`，然后根据结果转到"可填写字段"或"不可填写字段"并按照这些说明操作。

# 可填写字段
如果 PDF 有可填写表单字段：
- 从此文件的目录运行此脚本：`python scripts/extract_form_field_info.py <input.pdf> <field_info.json>`。它将创建一个 JSON 文件，其中包含以下格式的字段列表：
```
[
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "rect": ([左, 下, 右, 上] PDF 坐标中的边界框，y=0 是页面底部),
    "type": ("text"、"checkbox"、"radio_group" 或 "choice"),
  },
  // 复选框有 "checked_value" 和 "unchecked_value" 属性：
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "checkbox",
    "checked_value": (将字段设置为该值以选中复选框),
    "unchecked_value": (将字段设置为该值以取消选中复选框),
  },
  // 单选按钮组有一个 "radio_options" 列表，包含可能的选项。
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "radio_group",
    "radio_options": [
      {
        "value": (将字段设置为该值以选择此单选选项),
        "rect": (此选项单选按钮的边界框)
      },
      // 其他单选选项
    ]
  },
  // 多选字段有一个 "choice_options" 列表，包含可能的选项：
  {
    "field_id": (字段的唯一 ID),
    "page": (页码，从 1 开始),
    "type": "choice",
    "choice_options": [
      {
        "value": (将字段设置为该值以选择此选项),
        "text": (选项的显示文本)
      },
      // 其他选项
    ],
  }
]
```
- 使用此脚本将 PDF 转换为 PNG（每页一张图片）（从此文件的目录运行）：
`python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>`
然后分析图片以确定每个表单字段的用途（确保将边界框 PDF 坐标转换为图片坐标）。
- 创建一个 `field_values.json` 文件，格式如下，包含要为每个字段输入的值：
```
[
  {
    "field_id": "last_name", // 必须与 `extract_form_field_info.py` 中的 field_id 匹配
    "description": "用户的姓氏",
    "page": 1, // 必须与 field_info.json 中的 "page" 值匹配
    "value": "Simpson"
  },
  {
    "field_id": "Checkbox12",
    "description": "如果用户年满 18 岁则选中的复选框",
    "page": 1,
    "value": "/On" // 如果是复选框，使用其 "checked_value" 值来选中它。如果是单选按钮组，使用 "radio_options" 中的某个 "value" 值。
  },
  // 更多字段
]
```
- 从此文件的目录运行 `fill_fillable_fields.py` 脚本以创建填写好的 PDF：
`python scripts/fill_fillable_fields.py <input pdf> <field_values.json> <output pdf>`
此脚本将验证您提供的字段 ID 和值是否有效；如果打印错误消息，请更正相应的字段并重试。

# 不可填写字段
如果 PDF 没有可填写表单字段，您将添加文本注释。首先尝试从 PDF 结构中提取坐标（更准确），然后在需要时回退到视觉估计。

## 步骤 1：首先尝试结构提取

运行此脚本以提取带有精确 PDF 坐标的文本标签、线条和复选框：
`python scripts/extract_form_structure.py <input.pdf> form_structure.json`

这将创建一个包含以下内容的 JSON 文件：
- **labels**：每个文本元素及其精确坐标（PDF 点中的 x0、top、x1、bottom）
- **lines**：定义行边界的水平线
- **checkboxes**：作为复选框的小矩形（带中心坐标）
- **row_boundaries**：从水平线计算的行顶部/底部位置

**检查结果**：如果 `form_structure.json` 有有意义的标签（与表单字段对应的文本元素），请使用**方法 A：基于结构的坐标**。如果 PDF 是扫描/基于图片的，并且没有或很少有标签，请使用**方法 B：视觉估计**。

---

## 方法 A：基于结构的坐标（首选）

在 `extract_form_structure.py` 在 PDF 中找到文本标签时使用此方法。

### A.1：分析结构

读取 form_structure.json 并识别：

1. **标签组**：形成单个标签的相邻文本元素（例如，"Last" + "Name"）
2. **行结构**：具有相似 `top` 值的标签在同一行
3. **字段列**：输入区域在标签结束后开始（x0 = label.x1 + 间隙）
4. **复选框**：直接使用结构中的复选框坐标

**坐标系**：PDF 坐标，其中 y=0 在页面顶部，y 向下增加。

### A.2：检查缺失元素

结构提取可能无法检测到所有表单元素。常见情况：
- **圆形复选框**：仅将矩形检测为复选框
- **复杂图形**：装饰元素或非标准表单控件
- **褪色或浅色元素**：可能无法提取

如果您在 PDF 图片中看到 form_structure.json 中没有的表单字段，您需要对这些特定字段使用**视觉分析**（参见下面的"混合方法"）。

### A.3：使用 PDF 坐标创建 fields.json

对于每个字段，从提取的结构计算输入坐标：

**文本字段：**
- entry x0 = label x1 + 5（标签后的小间隙）
- entry x1 = 下一个标签的 x0，或行边界
- entry top = 与标签 top 相同
- entry bottom = 下面的行边界线，或 label bottom + row_height

**复选框：**
- 直接使用 form_structure.json 中的复选框矩形坐标
- entry_bounding_box = [checkbox.x0, checkbox.top, checkbox.x1, checkbox.bottom]

使用 `pdf_width` 和 `pdf_height` 创建 fields.json（表示 PDF 坐标）：
```json
{
  "pages": [
    {"page_number": 1, "pdf_width": 612, "pdf_height": 792}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "姓氏输入字段",
      "field_label": "Last Name",
      "label_bounding_box": [43, 63, 87, 73],
      "entry_bounding_box": [92, 63, 260, 79],
      "entry_text": {"text": "Smith", "font_size": 10}
    },
    {
      "page_number": 1,
      "description": "美国公民是复选框",
      "field_label": "Yes",
      "label_bounding_box": [260, 200, 280, 210],
      "entry_bounding_box": [285, 197, 292, 205],
      "entry_text": {"text": "X"}
    }
  ]
}
```

**重要**：使用 `pdf_width`/`pdf_height` 和 form_structure.json 中的坐标。

### A.4：验证边界框

在填写之前，检查您的边界框是否有错误：
`python scripts/check_bounding_boxes.py fields.json`

这会检查相交的边界框和对于字体大小来说太小的输入框。在填写之前修复任何报告的错误。

---

## 方法 B：视觉估计（回退）

在 PDF 是扫描/基于图片的且结构提取没有找到可用文本标签时使用此方法（例如，所有文本显示为"(cid:X)"模式）。

### B.1：将 PDF 转换为图片

`python scripts/convert_pdf_to_images.py <input.pdf> <images_dir/>`

### B.2：初始字段识别

检查每个页面图片以识别表单部分并获取字段位置的**粗略估计**：
- 表单字段标签及其大致位置
- 输入区域（线条、框或文本输入的空白区域）
- 复选框及其大致位置

对于每个字段，记下大致的像素坐标（它们还不需要精确）。

### B.3：缩放细化（对准确性至关重要）

对于每个字段，在估计位置周围裁剪一个区域以精确细化坐标。

**使用 ImageMagick 创建缩放裁剪：**
```bash
magick <page_image> -crop <width>x<height>+<x>+<y> +repage <crop_output.png>
```

其中：
- `<x>, <y>` = 裁剪区域的左上角（使用粗略估计减去边距）
- `<width>, <height>` = 裁剪区域的大小（字段区域加上每侧约 50px 边距）

**示例：** 要细化估计在 (100, 150) 附近的"姓名"字段：
```bash
magick images_dir/page_1.png -crop 300x80+50+120 +repage crops/name_field.png
```

（注意：如果 `magick` 命令不可用，请尝试使用相同参数的 `convert`）。

**检查裁剪的图片**以确定精确坐标：
1. 确定输入区域开始的确切像素（在标签之后）
2. 确定输入区域结束的位置（在下一个字段或边缘之前）
3. 确定输入线/框的顶部和底部

**将裁剪坐标转换回完整图片坐标：**
- full_x = crop_x + crop_offset_x
- full_y = crop_y + crop_offset_y

示例：如果裁剪从 (50, 120) 开始，且输入框在裁剪内从 (52, 18) 开始：
- entry_x0 = 52 + 50 = 102
- entry_top = 18 + 120 = 138

**对每个字段重复**，在可能的情况下将附近的字段分组到单个裁剪中。

### B.4：使用细化坐标创建 fields.json

使用 `image_width` 和 `image_height` 创建 fields.json（表示图片坐标）：
```json
{
  "pages": [
    {"page_number": 1, "image_width": 1700, "image_height": 2200}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "姓氏输入字段",
      "field_label": "Last Name",
      "label_bounding_box": [120, 175, 242, 198],
      "entry_bounding_box": [255, 175, 720, 218],
      "entry_text": {"text": "Smith", "font_size": 10}
    }
  ]
}
```

**重要**：使用 `image_width`/`image_height` 和缩放分析中的细化像素坐标。

### B.5：验证边界框

在填写之前，检查您的边界框是否有错误：
`python scripts/check_bounding_boxes.py fields.json`

这会检查相交的边界框和对于字体大小来说太小的输入框。在填写之前修复任何报告的错误。

---

## 混合方法：结构 + 视觉

在结构提取适用于大多数字段但遗漏某些元素（例如，圆形复选框、不寻常的表单控件）时使用此方法。

1. **使用方法 A** 针对在 form_structure.json 中检测到的字段
2. **将 PDF 转换为图片** 以进行缺失字段的视觉分析
3. **使用缩放细化**（来自方法 B）针对缺失字段
4. **合并坐标**：对于来自结构提取的字段，使用 `pdf_width`/`pdf_height`。对于视觉估计的字段，您必须将图片坐标转换为 PDF 坐标：
   - pdf_x = image_x * (pdf_width / image_width)
   - pdf_y = image_y * (pdf_height / image_height)
5. **在 fields.json 中使用单一坐标系** - 将所有坐标转换为 PDF 坐标，使用 `pdf_width`/`pdf_height`

---

## 步骤 2：填写前验证

**始终在填写前验证边界框：**
`python scripts/check_bounding_boxes.py fields.json`

这会检查：
- 相交的边界框（会导致文本重叠）
- 对于指定字体大小来说太小的输入框

在继续之前修复 fields.json 中的任何错误。

## 步骤 3：填写表单

填写脚本自动检测坐标系并处理转换：
`python scripts/fill_pdf_form_with_annotations.py <input.pdf> fields.json <output.pdf>`

## 步骤 4：验证输出

将填写好的 PDF 转换为图片并验证文本位置：
`python scripts/convert_pdf_to_images.py <output.pdf> <verify_images/>`

如果文本位置不正确：
- **方法 A**：检查您是否使用 form_structure.json 中的 PDF 坐标，使用 `pdf_width`/`pdf_height`
- **方法 B**：检查图片尺寸是否匹配且坐标是准确的像素
- **混合**：确保视觉估计字段的坐标转换正确
