# eu-einvoice：欧盟电子发票 Claude Skill

[English](README.md)

这是一个 Claude skill（同时打包成 Claude Code 插件），用来**生成、校验、读取和转换欧盟结构化电子发票**（EN 16931 标准）。支持的格式有：**XRechnung**（UBL 和 CII）、**Peppol BIS Billing 3.0**、**ZUGFeRD / Factur-X** 混合 PDF，以及普通的 UBL 2.1 和 UN/CEFACT CII。

用平常的话对 Claude 说就行，比如"帮我给科隆市开一张 XRechnung""为什么我的 Peppol 发票被拒，报 BR-CO-15""供应商发来的 xrechnung.xml 里写了什么"。Claude 会调用 skill 自带的工具来处理，不用自己手写 XML：

- **金额全部自动算**：行金额、按税类和税率分组的增值税、各级合计、预付款、折扣和附加费，都精确到分，符合 EN 16931（BR-CO-10~17）和 Peppol（R040、R120）的要求。算错金额是电子发票被拒最常见的原因。
- **用官方规则校验**：和收票平台用的是同一套规则，包括 XSD、CEN EN 16931 Schematron、KoSIT XRechnung、OpenPeppol BIS 3.0。全部通过 Saxon-HE（`saxonche`）在纯 Python 里运行，**不需要 Java**。规则包固定在具体版本，下载时用 SHA-256 校验。
- **报错时告诉你怎么改**：每条问题都列出官方规则编号、原文、出错位置，以及按发票数据给出的修改建议。
- **补查官方规则不查的编号**：校验 Leitweg-ID、SIREN、SIRET、法国和比利时税号、GLN/GTIN 的校验位。这些编号写错了，发票照样能通过校验，却送不到收票方。
- **读取和转换发票**：收到的 XML 或 Factur-X/ZUGFeRD PDF 可以转成 JSON，也可以渲染成按卖方语言（德/法/荷/意/西/英）排版的 HTML 或 PDF。格式互转（UBL ↔ CII、ZUGFeRD → XRechnung 等）时保留原发票的金额。
- **生成 Factur-X / ZUGFeRD PDF**：输出 PDF/A-3，嵌入字体、sRGB 颜色配置和 Factur-X 元数据，并内嵌 `factur-x.xml`；也可以把 XML 嵌进你自己排版好的 PDF。

## 安装

**Claude Code**（插件市场）：

```
/plugin marketplace add uulucky/claude-skill-eu-einvoice
/plugin install eu-einvoice@uulucky-skills
```

**claude.ai 网页版 / Claude 桌面 App**：从 [Releases](https://github.com/uulucky/claude-skill-eu-einvoice/releases/latest) 下载 `eu-einvoice.skill`，拖进对话后点 "Save skill"，也可以在设置的 Skills 页面上传。

**手动安装**：把 `skills/eu-einvoice/` 复制到 `~/.claude/skills/eu-einvoice/`。

**环境要求**：Python 3.9 以上。第一次使用时，skill 会按 `requirements.txt` 自动建虚拟环境。官方规则包在第一次校验时下载到 `~/.cache/eu-einvoice/rules`，可以用环境变量 `EINVOICE_RULES_DIR` 改位置。

## 用法示例

- "Die Stadt Köln will eine XRechnung, Leitweg-ID …"：生成 XRechnung，并通过 XSD + CEN + KoSIT 三层校验。
- "比利时客户把 invoice-1187.xml 退回来了，报 R003、CL008、BR-CO-15"：解释每个错误，重新生成修正后的 Peppol 发票并再次校验。
- "给法国客户开一张 Factur-X PDF"：生成 PDF/A-3，内嵌 `factur-x.xml`，PDF 和 XML 都做校验。
- "供应商发来 xrechnung.xml，打不开"：告诉你应付金额、到期日和 IBAN，并生成可打印的 PDF。
- "把这张 ZUGFeRD PDF 转成 XRechnung UBL，要传 ZRE 平台"：缺的必填字段会先问你，补齐后转换并校验。

不通过 Claude，也可以直接用命令行，命令见英文 README。

## 局限

- 只负责生成和校验文件，**不负责发送**。Peppol 要通过接入点（access point）发送，德国政府平台要上传或走 Peppol 通道。
- PDF/A-3 按规范生成，正式认证需要用 [veraPDF](https://verapdf.org) 检查。
- 不支持非 EN 16931 的各国本地格式：意大利 FatturaPA、波兰 KSeF、西班牙 Verifactu、匈牙利 NAV、希腊 myDATA、印度 GST。也不支持 Factur-X 的 MINIMUM、BASIC WL、EXTENDED 档次。
- 这不是税务建议。选哪种增值税类别、免税理由，请咨询你的会计。

## 许可证

MIT，见 [LICENSE](LICENSE)。
