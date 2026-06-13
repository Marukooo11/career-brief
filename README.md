# Career Brief：可配置的求职情报简报

Career Brief 是一个面向求职者、转岗者和作品集准备者的 AI 行业情报简报模板。它可以围绕你配置的目标岗位，定时收集近 30 天的行业信息、岗位经验、学习路径和真实案例，并通过邮件推送中文摘要。

默认示例使用了两个匿名方向：**（示例方向 A）** 和 **（示例方向 B）**。你可以把 `config/topics.yml` 改成自己的求职方向，例如数据分析师、海外增长 PM、AI 教育产品经理、B2B SaaS 产品经理、前端工程师等。

如果仓库是公开的，建议不要在默认配置里暴露过于具体的个人求职方向；可以使用私有 fork、手动 workflow 输入，或在 `topic_context` 中写更泛化的描述。

这个项目验证的是一条求职准备链路：

```text
信息输入 -> 行业语感 -> 面试观点 -> 作品集机会
```

## 适合谁使用

- 正在转岗，需要快速熟悉一个新行业或新岗位的人。
- 正在求职，希望持续积累面试案例、岗位黑话和行业表达的人。
- 正在准备作品集，希望从真实案例里寻找选题的人。
- 想用 GitHub Actions 搭一个轻量自动化信息流的人。

## 它能做什么

- **定时推送**：通过 GitHub Actions 每 2 天中午运行一次，也支持手动触发。
- **自定义求职方向**：在 `config/topics.yml` 里配置岗位名称和搜索关键词。
- **多来源搜索**：围绕岗位职责、国内内容平台、学习路径、从业者经验分别检索。
- **中文摘要**：把检索结果整理成中文邮件，并解释内容与求职方向的关系。
- **按主题拆分邮件**：多个求职方向可以分别发送，避免一封邮件过长。
- **Artifacts 归档**：每次运行会保存 Markdown / JSON 结果，方便之后复盘。

## 快速开始

### 1. Fork 或使用这个模板

Fork 本仓库，或者创建新仓库后复制这些文件。

### 2. 配置你的求职方向

编辑 `config/topics.yml`。每个 topic 是一个求职方向：

```yaml
topics:
  - name: "（示例方向 A）"
    topic_context: "用户正在准备某个方向，重点关注 具体业务链路、工作流、效率工具、用户场景、商业指标和岗位能力要求。"
    query_role: "AI vertical product manager responsibilities industry workflow automation AI assistant B2B SaaS job description"
    query_china_market: "AI 垂直行业 产品经理 业务流程 AI 工作台 效率工具 岗位 经验"
    query_learning: "AI product manager vertical industry workflow automation learning path business process AI assistant"
    query_experience: "AI product manager vertical industry workflow automation experience case study lessons learned"
```

字段含义：

- `name`：邮件里显示的主题名称。
- `topic_context`：可选。告诉模型你的求职背景和关注场景，用来生成更贴合的关联理由；公开仓库中建议写泛化描述。
- `query_role`：岗位职责、JD、能力模型。
- `query_china_market`：中文平台、国内经验帖、行业讨论。
- `query_learning`：学习路径、能力提升、入门路线。
- `query_experience`：从业者经验、面经、工作日常、复盘文章。

你也可以参考 `config/topics.example.yml`，把示例替换成自己的目标岗位。

### 3. 配置邮件 Secrets

在 GitHub 仓库里打开：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

添加这些必填项：

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_TO
```

常见 SMTP 配置：

```text
Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587
QQ Mail: SMTP_HOST=smtp.qq.com, SMTP_PORT=465 or 587
Outlook: SMTP_HOST=smtp.office365.com, SMTP_PORT=587
163 Mail: SMTP_HOST=smtp.163.com, SMTP_PORT=465 or 994
```

`SMTP_PASSWORD` 通常应该填写邮箱的 app password / SMTP 授权码，而不是邮箱登录密码。

可选邮件配置：

```text
EMAIL_FROM
EMAIL_SUBJECT
```

如果 `EMAIL_FROM` 为空，脚本会使用 `SMTP_USERNAME`。

### 4. 配置可选数据源 Key

没有 API key 时，项目也可以以基础模式运行；配置 key 后，搜索和摘要质量会更好。

```text
OPENAI_API_KEY
GOOGLE_API_KEY
GEMINI_API_KEY
BRAVE_API_KEY
SERPER_API_KEY
EXA_API_KEY
SCRAPECREATORS_API_KEY
XAI_API_KEY
BSKY_HANDLE
BSKY_APP_PASSWORD
```

如果配置了 `OPENAI_API_KEY`，临时输入的中文主题会被改写成更适合英文网页、社媒和论坛搜索的 query，并且来源摘要会更完整。

### 5. 手动测试

打开：

```text
Actions -> Career Brief -> Run workflow
```

手动运行时可以填写 `topics` 输入框，用逗号或换行临时覆盖 `config/topics.yml`。不填写则使用配置文件中的 topics。

## 简报结构

当前邮件会按主题输出：

```text
主题
本次搜索拆分
找到多少条线索 / 来源分布
这个岗位大概做什么
需要补的能力，以及怎么补
可转化成简历/作品集的方向
如何新增能力 / 学习路径：相关来源观点
帖子经验 / 从业者观点：相关来源观点
1. 来源标题
   主要内容
   与搜索主题的关联
   推荐阅读理由
   来源
   信号分
   链接
```

项目希望把简报从“信息罗列”推进到“求职资产沉淀”，因此更关注：

- 是否发现了值得深读的行业案例。
- 是否提炼了可用于面试表达的观点。
- 是否发现了可转化为作品集的产品机会。

## 默认示例：AI 产品经理求职情报

本仓库默认配置了两个匿名示例方向：

1. **（示例方向 A）**
   关注 AI 如何进入某个具体行业的业务链路，例如行业工作台、AI 助手、自动化流程、内容/素材生成、客服辅助、数据分析和决策支持等场景。

2. **（示例方向 B）**
   关注 AI 内容生产、推荐分发、创作者社区、UGC 治理、社区增长、用户关系和内容质量等场景。

这些示例可以直接使用，也可以作为配置其他岗位的参考。对于真实求职方向，建议根据自己的目标岗位改写 `name`、`topic_context` 和各类 query。

## 迭代路线

### V1：稳定信息输入链路

已完成：

- 定时运行
- 主题配置
- 多来源搜索
- 中文摘要
- 来源相关性解释
- 邮件推送
- Markdown / JSON artifacts 归档

### V2：提升信息转化质量

计划补强：

1. **面试观点提炼**
   将重点案例转化为“观点 + 案例 + 面试表达话术”。

2. **行业黑话解释**
   对简报中出现的行业术语进行“含义 + 业务场景 + 面试使用方式”的解释。

3. **Markdown 案例库沉淀**
   将高价值案例按固定字段沉淀为 Markdown 条目，方便复制、归档，并后续转化为作品集素材。

案例库条目模板：

```markdown
## 案例库条目

- 案例名称：
- 公司 / 产品：
- 所属场景：
- 发生了什么：
- 为什么重要：
- 面试可讲观点：
- 可延展作品集方向：
- 原文链接：
- 收录日期：
```

## 定时规则

默认 workflow 每 2 天在北京时间 12:00 运行：

```yaml
cron: "0 4 */2 * *"
```

GitHub Actions 的 cron 使用 UTC，因此北京时间 12:00 对应 UTC 04:00。

## 技术来源与致谢

Career Brief 的信息检索能力参考并调用了 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)。本仓库主要在它的近 30 天信息检索能力之上，补充了面向求职场景的 topic 配置、中文邮件摘要、岗位相关性解释、GitHub Actions 定时运行和 artifacts 归档。

workflow 每次运行时会临时 clone upstream skill：

```yaml
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git .last30days-skill
```

因此，本仓库不直接复制 upstream skill 的代码；它更像是一个面向求职情报场景的轻量封装和使用模板。

## 本地 Dry Run

克隆 upstream skill 后可以本地测试：

```bash
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git .last30days-skill
python scripts/daily_last30days.py --skill-dir .last30days-skill --dry-run
```

Dry run 会打印消息，不会发送邮件。

## 公开仓库安全提醒

- 不要把邮箱密码或 API key 写进代码。
- 所有 token 和 key 都放在 GitHub Secrets。
- 不要提交 `artifacts/`、`.last30days-skill/`、`__pycache__/` 等运行产物。
- 如果任何 token 泄露，立即 revoke 并重新生成。

## License

MIT
