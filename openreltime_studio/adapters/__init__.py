"""Studio 适配层 — 唯一允许 ``import openreltime`` 的代码层。

负责把 ``openreltime`` 公共 API 的 Result 对象转换为 UI 可用的模型
（DataFrame → 表格数据、matplotlib Figure → Qt 画布、参数 → 等效 CLI 字符串）。
核心 API 签名变动只需在此层一处修改。
"""
