# Career Brief：面向转岗求职者的 AI 行业情报简报

Career Brief 是一个面向转岗求职者的 AI 行业情报简报工具。它可以围绕用户配置的目标岗位，定时收集近 30 天的公开信息，并将行业案例、岗位经验、学习路径和作品集机会整理成中文邮件。

这个项目不是单纯的信息聚合工具，而是希望帮助转岗求职者完成一条更清晰的求职准备链路：

```text
信息输入 -> 行业语感 -> 面试观点 -> 作品集机会
```

## 1. 项目概览

Career Brief 面向正在转岗、准备进入 AI 产品经理相关岗位的人群。

用户可以在配置文件中设置自己的目标方向，例如 AI 产品经理、AI 教育产品经理、B2B SaaS 产品经理、海外增长 PM、数据分析师等。系统会定时围绕这些方向搜索近 30 天的公开信息，并通过邮件推送结构化中文简报。

每期简报不仅会展示信息来源，也会解释：

* 这个内容和目标岗位有什么关系。
* 它能帮助用户理解什么业务问题。
* 它是否可以转化成面试观点。
* 它是否可以延展成作品集选题。

## 2. 背景与问题

在转岗 AI 产品经理的过程中，很多求职者遇到的困难并不是“不努力”，而是信息输入本身就很混乱。

常见问题包括：

1. **不知道应该搜什么**
   转岗者往往还不熟悉目标岗位的业务语境，很难判断哪些关键词、案例、行业讨论是有价值的。

2. **公开信息太分散**
   岗位JD、行业新闻、从业者经验、产品案例、学习路径分布在不同平台，手动搜索成本很高。

3. **信息看过但没有沉淀**
   很多内容只是被临时收藏，并没有进一步转化为面试表达、岗位理解或作品集素材。

4. **求职节奏难持续**
   转岗准备是一个长期过程。如果没有稳定的信息输入机制，容易出现三天打鱼两天晒网的状态。

Career Brief 试图解决的不是“帮用户自动找到工作”，而是帮助用户持续建立目标岗位所需的行业语感、案例储备和表达素材。

## 3. 目标用户与使用场景

### 目标用户

初始用户是我自己：一个正在从 AI 数据评估 / 质控相关工作，转向 AI 产品经理方向的求职者。

在这个个人场景基础上，项目也可以扩展到更广泛的转岗人群：

* 想转 AI 产品经理，但缺少行业案例积累的人。
* 想进入某个垂直行业，但还不了解业务链路的人。
* 正在准备作品集，需要持续寻找真实产品案例的人。
* 想用自动化方式建立个人求职信息流的人。

### 使用场景

典型使用场景是：

1. 用户在 `config/topics.yml` 中配置目标岗位方向。
2. GitHub Actions 按固定时间运行任务。
3. 系统围绕目标方向搜索近 30 天公开信息。
4. 系统生成中文简报并发送到用户邮箱。
5. 用户从简报中挑选值得深读的案例、观点和作品集机会。
6. 用户将高价值内容沉淀到自己的面试笔记或作品集案例库中。

## 4. 产品目标

Career Brief 的核心目标不是“每天给用户更多链接”，而是让每期简报至少帮助用户沉淀出：

* **1 个值得深读的行业 / 产品案例**
* **1 个可以用于面试表达的观点**
* **1 个可以延展为作品集的机会点**

因此，简报的评价标准不是信息数量，而是信息是否能继续转化。

每期简报理想上应该回答三个问题：

1. 今天有什么案例值得看？
2. 这个案例能帮我理解什么岗位能力？
3. 它能不能变成我的面试表达或作品集选题？

## 5. MVP 方案

当前 MVP 聚焦于搭建一条稳定的求职信息输入链路。

已实现能力包括：

### 1. 定时推送

通过 GitHub Actions 定时运行任务，每 2 天自动生成一次简报，也支持手动触发。

### 2. 主题配置

用户可以在 `config/topics.yml` 中配置多个求职方向。每个 topic 可以包含：

* `name`：方向名称。
* `topic_context`：用户背景和关注场景。
* `query_role`：岗位职责、JD 和能力模型。
* `query_china_market`：中文平台、国内经验帖和行业讨论。
* `query_learning`：学习路径、能力提升和入门路线。
* `query_experience`：从业者经验、面经、工作日常和复盘文章。

### 3. 多来源搜索

系统会围绕不同搜索维度获取近 30 天的公开信息，避免只依赖单一关键词或单一平台。

### 4. 中文摘要

检索结果会被整理成中文简报，降低用户阅读英文网页、论坛和社媒内容的门槛。

### 5. 相关性解释

每条信息不只展示标题和链接，也会解释它和当前求职方向的关系，帮助用户判断是否值得继续深读。

### 6. 邮件推送与结果归档

简报会通过邮件推送，同时保存 Markdown / JSON 结果，方便后续复盘和沉淀。

## 6. 简报信息结构

当前简报结构围绕“求职资产沉淀”设计，而不是简单的信息罗列。

一封简报主要包括：

```text
主题
本次搜索拆分
找到多少条线索 / 来源分布
这个岗位大概做什么
需要补的能力，以及怎么补
可转化成简历 / 作品集的方向
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

后续希望进一步优化为更产品化的信息结构：

### 今日重点案例

从本期信息中选出最值得深读的案例，并解释它对应的业务场景。

### 行业黑话解释

提取简报中反复出现的行业术语，解释它的含义、使用场景，以及在面试中应该如何表达。

### 从业者 / 岗位经验

整理来自岗位 JD、经验帖、论坛讨论中的能力要求和真实工作内容。

### 面试可讲观点

将案例和行业讨论转化为更适合面试表达的观点。

示例：

```text
我观察到某类 AI 产品的核心价值并不是替代人工，而是降低用户从需求到初稿之间的启动成本。
```

### 作品集机会点

把高价值案例转化成可以继续拆解的作品集选题。

示例：

```text
可以设计一个面向垂直行业新手的 AI 工作流助手，重点展示用户场景拆解、核心流程、信息架构和评估指标。
```

## 7. 内容质量策略

为了避免简报变成低质量链接堆砌，项目需要建立内容质量策略。

### 来源优先级

优先保留：

1. 真实产品案例
2. 一线从业者经验
3. 具体岗位 JD / 招聘需求
4. 行业报告或公司博客
5. 高质量论坛讨论
6. 学习路径和技能总结

降低优先级：

1. 纯营销文章
2. 信息重复的新闻转载
3. 没有具体案例的泛泛观点
4. 与目标岗位关系很弱的内容

### 过滤标准

一条内容是否值得进入简报，至少需要满足以下任一条件：

* 提供了一个具体产品 / 公司 / 行业案例。
* 解释了某个岗位能力要求。
* 出现了可复用的业务场景。
* 能帮助用户理解某个行业黑话。
* 可以转化为面试观点或作品集选题。

### 黑话解释标准

行业术语解释不只解释“是什么意思”，还应该说明：

* 它在哪些业务场景中出现。
* 它和目标岗位有什么关系。
* 面试时应该如何自然使用。
* 它背后反映了什么业务问题。

## 8. 使用反馈与成功指标

Career Brief 的成功不应该只看“邮件是否发送成功”，而应该看它是否真的帮助用户完成求职准备。

可以追踪的指标包括：

### 使用行为指标

* 每周收到多少期简报。
* 每期点开多少篇原文。
* 是否持续使用 7 天 / 14 天 / 30 天。
* 是否主动调整 topics 配置。

### 内容沉淀指标

* 每周沉淀多少个案例。
* 每周整理多少个面试观点。
* 每周生成多少个作品集机会点。
* 有多少内容被加入个人案例库。

### 求职准备指标

* 是否能更清楚地描述目标岗位。
* 是否能讲出具体行业案例。
* 是否能把案例转化为产品分析。
* 是否能从简报中提炼作品集选题。

## 9. 迭代路线

### V1：稳定信息输入链路

已完成：

* 定时运行
* 主题配置
* 多来源搜索
* 中文摘要
* 来源相关性解释
* 邮件推送
* Markdown / JSON artifacts 归档

### V2：提升信息转化质量

下一阶段重点不是增加更多信息源，而是提升信息转化质量。

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

## 10. 技术实现与部署

### 10.1 技术来源

Career Brief 的信息检索能力参考并调用了 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)。

本仓库主要在它的近 30 天信息检索能力之上，补充了面向求职场景的 topic 配置、中文邮件摘要、岗位相关性解释、GitHub Actions 定时运行和 artifacts 归档。

workflow 每次运行时会临时 clone upstream skill：

```bash
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git .last30days-skill
```

因此，本仓库不直接复制 upstream skill 的代码；它更像是一个面向求职情报场景的轻量封装和使用模板。

### 10.2 配置求职方向

编辑 `config/topics.yml`。每个 topic 是一个求职方向。

示例：

```yaml
topics:
  - name: "（示例方向 A）"
    topic_context: "用户正在准备某个方向，重点关注具体业务链路、工作流、效率工具、用户场景、商业指标和岗位能力要求。"
    query_role: "AI vertical product manager responsibilities industry workflow automation AI assistant B2B SaaS job description"
    query_china_market: "AI 垂直行业 产品经理 业务流程 AI 工作台 效率工具 岗位 经验"
    query_learning: "AI product manager vertical industry workflow automation learning path business process AI assistant"
    query_experience: "AI product manager vertical industry workflow automation experience case study lessons learned"
```

字段含义：

* `name`：邮件里显示的主题名称。
* `topic_context`：可选。告诉模型你的求职背景和关注场景，用来生成更贴合的关联理由；公开仓库中建议写泛化描述。
* `query_role`：岗位职责、JD、能力模型。
* `query_china_market`：中文平台、国内经验帖、行业讨论。
* `query_learning`：学习路径、能力提升、入门路线。
* `query_experience`：从业者经验、面经、工作日常、复盘文章。

### 10.3 配置 GitHub Secrets

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

### 10.4 配置可选数据源 Key

没有 API key 时，项目也可以以基础模式运行；配置 key 后，搜索和摘要质量会更好。

可选项包括：

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

### 10.5 手动测试

打开：

```text
Actions -> Career Brief -> Run workflow
```

手动运行时可以填写 `topics` 输入框，用逗号或换行临时覆盖 `config/topics.yml`。不填写则使用配置文件中的 topics。

### 10.6 定时规则

默认 workflow 每 2 天在北京时间 12:00 运行：

```yaml
cron: "0 4 */2 * *"
```

GitHub Actions 的 cron 使用 UTC，因此北京时间 12:00 对应 UTC 04:00。

### 10.7 本地 Dry Run

克隆 upstream skill 后可以本地测试：

```bash
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git .last30days-skill
python scripts/daily_last30days.py --skill-dir .last30days-skill --dry-run
```

Dry run 会打印消息，不会发送邮件。

## 公开仓库安全提醒

* 不要把邮箱密码或 API key 写进代码。
* 所有 token 和 key 都放在 GitHub Secrets。
* 不要提交 `artifacts/`、`.last30days-skill/`、`__pycache__/` 等运行产物。
* 如果任何 token 泄露，立即 revoke 并重新生成。
* 如果简报内容涉及个人求职计划、目标公司或真实搜索方向，建议不要将生成结果上传到公开仓库。

## License

MIT
