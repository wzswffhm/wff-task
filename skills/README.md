# wff-skills

个人 Codex skills 仓库，用于多套 skill 的版本管理与跨机器分发。

## 仓库结构

```text
wff-skills/
├── README.md
├── harbor-skill/
│   ├── SKILL.md
│   └── references/      # 该 skill 的参考文件
├── harbor-eval-bundle/
│   ├── SKILL.md
│   ├── references/
│   └── templates/
└── …（后续可继续添加其他 skill）
```

每个 skill 一个目录，目录内必须有带 `name` + `description` frontmatter 的 `SKILL.md`。

## 安装到新机器

方式一（推荐）：在 Codex 里说“从 wff-skills 仓库安装 harbor-skill”，走 skill-installer 自动安装到 `~/.codex/skills/`。

方式二（手动）：

```powershell
git clone https://github.com/wzswffhm/wff-skills.git
Copy-Item -Recurse wff-skills\harbor-skill "$env:USERPROFILE\.codex\skills\harbor-skill"
```

装好后重启 Codex 会话生效。

## 更新流程

```powershell
git add -A
git commit -m "描述改动"
git push
```

## 注意

- 仓库为私有仓库，包含内部流程细节，勿公开
- 修改 `description` 会影响 skill 触发，改后建议新会话验证
