<!-- 描述 / Description: 一段话说清这次改动做了什么、为什么。 -->

## 改动内容 / What does this PR do?

-

## 动机 / Why?

-

## 自查清单 / Checklist

- [ ] `python -m ruff check . --select F,E9` 通过
- [ ] `python -m mypy openreltime_studio` 通过
- [ ] `python tools/check_i18n.py` 通过
- [ ] `QT_QPA_PLATFORM=offscreen python -m pytest -q` 通过
- [ ] 面向用户的变更已同步更新 `CHANGELOG.md` 与 `CHANGELOG-zh.md`
- [ ] 未引入裸索引安装说明（两个发行版均未上包索引，见 test_docs_hygiene）
- [ ] 界面文案改动已同时更新 `locales/en/` 与 `locales/zh/`
