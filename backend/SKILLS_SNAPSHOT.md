<available_skills>
  <skill>
    <name>satellite-param-analyzer</name>
    <description>卫星遥测参数智能分析助手。支持参数发现、电压/电流/温度范围判断（包括低于、高于、区间）、卫星时间秒递增检查、LOG增长分析、飞轮转速跳变检测、导航通信异常识别。当用户问“是否有低于28V”、“是否控制在X-Y之间”、“是否满足20±0.05”等问题时，必须使用本技能。本技能还支持在特定通电条件下（如成像处理箱和焦面均通电）进行数据筛选，并支持参数代码范围（如WD-C001——WD-C015）自动展开。</description>
    <location>./skills/satellite-param-ana/SKILL.md</location>
  </skill>
  <skill>
    <name>table-diff</name>
    <description>对比两份表格文件并先向用户展示差异摘要。用户需要比较 xlsx、xls 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。默认流程是先解析、分析、确认规则、执行比对，然后用 Markdown 表格 + 总结展示结果；只有用户明确要求时才生成 HTML、XLSX、Markdown 或 CSV 差异报告。</description>
    <location>./skills/table-diff/SKILL.md</location>
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
</available_skills>