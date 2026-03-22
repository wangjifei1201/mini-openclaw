# Doc Agent - 长期记忆

> 此文件记录Doc Agent的文档处理经验

## 初始化记录

- 创建时间：2024-01-01
- 初始状态：idle

## 常用处理方法

### PDF解析

```python
import fitz  # PyMuPDF
doc = fitz.open('document.pdf')
for page in doc:
    text = page.get_text()
```

### Word处理

```python
from docx import Document
doc = Document('document.docx')
for para in doc.paragraphs:
    print(para.text)
```

## 执行记录

暂无执行记录。