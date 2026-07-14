<available_skills>
  <skill>
    <name>satellite-telemetry-analyzer</name>
    <description>Use when 用户询问高分07B01/07C01/07D01卫星遥测参数分析，包括参数发现、阈值判断、区间判断、秒递增、LOG增长、飞轮跳变、温度代码范围或通信异常。</description>
    <location>./skills/satellite-telemetry-analyzer/SKILL.md</location>
  </skill>
  <skill>
    <name>table-diff</name>
    <description>对比两份表格文件并先向用户展示差异摘要。用户需要比较 xlsx、xls 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。默认流程是先解析、分析、确认规则、执行比对，然后用 Markdown 表格 + 总结展示结果；只有用户明确要求时才生成 HTML、XLSX、Markdown 或 CSV 差异报告。</description>
    <location>./skills/table-diff/SKILL.md</location>
  </skill>
  <skill>
    <name>real-estate-tender-extraction</name>
    <description>Use when 需要从地产招标文件、招标公告、投标人须知、评标办法、合同条款、技术标准、工程量清单、投标文件格式、答疑补遗中提取核心招标信息，或处理 real-estate tender documents、bid invitation、bidder instructions、evaluation methods、technical standards、bill-of-quantities、bid-format annexes。</description>
    <location>./skills/real-estate-tender-extraction/SKILL.md</location>
  </skill>
  <skill>
    <name>skill-creator</name>
    <description>创建有效技能的指南。当用户想要创建新技能（或更新现有技能）以使用专业知识、工作流程或工具集成扩展Claude的能力时使用此技能。</description>
    <location>./skills/skill-creator/SKILL.md</location>
  </skill>
  <skill>
    <name>table-generator</name>
    <description>根据用户自然语言描述生成表格。用于用户要求生成、设计、整理、导出表格，或需要 Markdown 预览后生成可下载的 xlsx/xls 文件时。</description>
    <location>./skills/table-generator/SKILL.md</location>
  </skill>
  <skill>
    <name>technical-bid-format-check</name>
    <description>Use when 需要进行技术标格式检查、暗标/明标格式审查、标书格式检查、施工技术标 Word 文件检查、招标文件格式要求核对、technical bid formatting，或需要输出 Markdown 人工确认报告。不直接修改 Word 文件。</description>
    <location>./skills/technical-bid-format-check/SKILL.md</location>
  </skill>
</available_skills>