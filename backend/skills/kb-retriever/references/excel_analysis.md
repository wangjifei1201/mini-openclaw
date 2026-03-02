# Excel 数据分析

> ⚠️ **使用本文档前请注意**：本文档应在实际分析 Excel 数据之前阅读，以了解正确的 pandas 读取方法。请配合 excel_analysis.md 一起使用。

使用 pandas 对 Excel 数据进行常规分析操作。

## 快速参考

| 任务 | 推荐工具 | 原因/命令/代码示例 |
|------|----------|----------|
| 纯文本提取（最常见） | pdftotext 命令 | 最快最简单 | `pdftotext input.pdf output.txt` |
| 需要保留布局 | pdftotext -layout | 保持原始排版 | `pdftotext -layout input.pdf output.txt` |
| 需要提取表格 | pdfplumber | 表格识别能力强 | `page.extract_tables()` |
| 扫描PDF（图片） | OCR (pytesseract) | 无其他选择 | 先转图片再OCR |
|------|----------|----------|

## 读取单个工作表

```python
import pandas as pd
# 读取第一个工作表（或指定工作表）
df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
# 只读取前几行查看结构
df_preview = pd.read_excel("data.xlsx", nrows=10)
print(df_preview.head())
```

## 读取指定工作表

```python
# 读取指定工作表
df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
```

## 只读取需要的列（提高性能）

```python
# 只读取需要的列（提高性能）
df = pd.read_excel("data.xlsx", usecols=["列1", "列2", "列3"])
```

## 查看基本统计信息

```python
# 基本统计信息
print(df.describe())
```

## 读取整个工作簿的所有工作表

```python
import pandas as pd
# 读取所有工作表
excel_file = pd.ExcelFile("workbook.xlsx")
for sheet_name in excel_file.sheet_names:
    df = pd.read_excel("workbook.xlsx", sheet_name=sheet_name)
    print(f"\n{sheet_name}:")
    print(df.head())
```

## 读取特定列

```python
# 读取特定列的数据
df_sales = pd.read_excel("data.xlsx", usecols=["sales", "quantity"])
```

## 处理大文件

```python
# 对于非常大的 Excel 文件，避免一次性读取整个文件
df = pd.read_excel("large_file.xlsx", nrows=1000)
```

## 数据过滤

```python
# 按条件过滤行
high_sales = df[df["sales"] > 10000]

# 多条件过滤
filtered = df[(df["sales"] > 10000) & (df["region"] == "North")]

# 使用 isin 过滤
selected = df[df["product"].isin(["A", "B", "C"])]
```

## 派生指标计算

```python
# 计算新列
df["profit_margin"] = (df["revenue"] - df["cost"]) / df["revenue"]

# 百分比计算
df["growth_rate"] = (df["current"] - df["previous"]) / df["previous"] * 100

# 累计求和
df["cumulative_sales"] = df["sales"].cumsum()
```

## 排序

```python
# 按单列排序
df_sorted = df.sort_values("sales", ascending=False)

# 按多列排序
df_sorted = df.sort_values(["region", "sales"], ascending=[True, False])
```

## 数据透视表

```python
# 创建数据透视表
pivot = pd.pivot_table(
    df,
    values="sales",
    index="region",
    columns="product",
    aggfunc="sum",
    fill_value=0
)

print(pivot)
```

## 统计分析

```python
# 基本统计
print(df.describe())

# 特定列统计
print(df["sales"].mean())
print(df["sales"].median())
print(df["sales"].std())

# 计数统计
print(df["category"].value_counts())
```

## 数据合并

```python
# 垂直合并多个 DataFrame
combined = pd.concat([df1, df2], ignore_index=True)

# 按公共列合并（类似 SQL JOIN）
merged = pd.merge(sales, customers, on="customer_id", how="left")
```

## 数据清洗

```python
# 删除重复行
df = df.drop_duplicates()

# 处理缺失值
df = df.fillna(0)  # 填充为 0
df = df.dropna()   # 删除含缺失值的行

# 去除空格
df["name"] = df["name"].str.strip()

# 类型转换
df["date"] = pd.to_datetime(df["date"])
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
```
