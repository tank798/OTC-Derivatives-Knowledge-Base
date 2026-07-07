# 多 Agent 研究记录

检索日期：2026-07-07

## Lane A：证监会 / 中证协 / 基金业协会

状态：完成。

已确认入口：

- 证监会主站：https://www.csrc.gov.cn/
- 证券期货法规数据库：https://neris.csrc.gov.cn/falvfagui/
- 法规库综合查询：https://neris.csrc.gov.cn/falvfagui/multipleFindController/indexJsp
- 法规库体系查询：https://neris.csrc.gov.cn/falvfagui/classifyController/indexJsp
- 中证协自律规则：https://www.sac.net.cn/zlgl/zlgz/
- 基金业协会法规查询：https://fg.amac.org.cn/

已写入 `data/processed/evidence_ledger.jsonl` 的核心法规包括：

- 《衍生品交易监督管理办法（试行）》
- 《证券公司收益互换业务管理办法》
- 《证券公司收益凭证发行管理办法》
- 《衍生品估值报告内容与格式指引》
- 《证券公司信用风险管理指引》
- 《公开募集证券投资基金投资者适当性管理细则》
- 《私募投资基金信息披露实施细则》
- 《基金经理兼任私募资产管理计划投资经理工作指引》

未解决缺口：

- `neris.csrc.gov.cn` 需要浏览器网络层探测真实检索接口。
- 中证协《证券公司场外期权业务管理办法》官方正文仍需定位。
- 中证协场外期权交易商名单、信用保护合约备案查询需要浏览器/API。
- `fg.amac.org.cn` 法规查询站需要浏览器/API。

## Lane B：央行 / 外汇局 / 交易商协会 / 中国货币网

状态：完成。

已确认入口：

- 央行部门规章：https://www.pbc.gov.cn/tiaofasi/144941/144957/index.html
- 外汇局政策法规：https://www.safe.gov.cn/safe/zcfg/index.html
- 交易商协会自律规则：https://www.nafmii.org.cn/zlgl/zlgz/
- 交易商协会标准协议文本：https://www.nafmii.org.cn/zlgl/bzxy/bzxywb/
- 交易商协会 CRM 业务规则：https://www.nafmii.org.cn/cpxl/xyfxhsgjcrm/ywgz/
- 中国货币网政策法规：https://www.chinamoney.com.cn/chinese/zcfg/
- 中国货币网外汇业务规则：https://www.chinamoney.com.cn/chinese/whywgz/
- 中国货币网本币业务规则：https://www.chinamoney.com.cn/chinese/bbywgz/

中国货币网已识别接口：

- 栏目映射：`/chinese/cxsymb/index.html`
- 列表接口：`POST /ags/ms/cm-s-notice-query/contents`
- 附件接口：`/ags/ms/cm-s-notice-query/txtAttachmentInfo`
- 附件下载：`/dqs/cm-s-notice-query/fileDownLoad.do?...`

关键 channelId：

- 政策法规：PBOC `2862`，SAFE `2863`，CFETS `2864`，交易商协会 `2865`
- 外汇规则：产品指引 `7496`，人民币外汇 `7497`，外币对 `7498`，外币利率 `7499`，做市 `7502`，应急 `7503`
- 本币/债券/衍生品：债券交易基本规则 `7513`，债券回购 `7508`，债券借贷 `7516`，跨境互联互通 `7519`，利率互换 `7523`，利率期权 `7524`，远期利率协议 `7525`，债券远期 `7526`，CRMW `7527`，CDS `7528`，衍生品对外开放 `7529`

未解决缺口：

- 交易商协会和中国货币网大量核心规则在 PDF/DOC/DOCX 附件里，需要批量下载和解析。
- 中国货币网基准数据页需要拆 XHR 接口。
- 外汇局“现行有效外汇管理主要法规目录”附件尚未解析。
- 央行还需补公告、规范性文件、金融市场司文件，不能只抓部门规章。
- 需要建立废止/替代关系表。

## Lane C：交易所和市场基础设施

状态：完成。

已确认入口：

- 上交所规则总览：https://www.sse.com.cn/lawandrules/sselawsrules2025/overview/
- 深交所法律规则：https://www.szse.cn/lawrules/
- 北交所规则页：https://www.bse.cn/rules.html
- 中金所业务规则：http://www.cffex.com.cn/ywgz/
- 上期所规则：https://www.shfe.com.cn/rules/
- 能源中心规则：https://www.ine.cn/rules/
- 大商所主页：http://www.dce.com.cn/
- 郑商所法律及规则：https://www.czce.com.cn/cn/flfg/H077005index_1.htm
- 广期所主页：https://www.gfex.com.cn/
- 中证登法律规则：https://www.chinaclear.cn/zdjs/flfg/law.shtml
- 中债登业务规则：https://www.chinabond.com.cn/sczy/sczy_ywwj/ywwj_ywgz/
- 上清所规则指南-业务规则：https://www.shclearing.com.cn/cpyyw/gzzn/ywgz/

已写入 `data/processed/evidence_ledger.jsonl` 的核心规则包括：

- 《深圳证券交易所交易规则（2026年修订）》
- 《深圳证券交易所融资融券交易实施细则（2023年修订）》
- 《深圳证券交易所资产支持证券挂牌条件审核业务指引第2号：审核重点关注事项》
- 《股票期权试点风险控制管理办法》
- 《中国金融期货交易所交易规则》
- 《中国金融期货交易所交易细则》
- 《中国金融期货交易所结算细则》
- 《中国金融期货交易所国债期货合约期转现交易细则》
- 《郑州商品交易所交易规则》
- 《郑州商品交易所期货结算管理办法》
- 《郑州商品交易所期权交易管理办法》
- 《郑州商品交易所期货交易管理办法》
- 中证登债券通用质押式回购交易结算委托协议/风险揭示书必备条款通知
- 上清所境外机构投资者债券回购交易清算结算业务规则/指南通知
- 上清所柜台债券登记托管结算业务实施细则通知
- 上清所银行间债券市场通用回购交易清算业务通知
- 上清所集中清算业务违约处置指引（2024年版）

未解决缺口：

- 上交所规则树已确认，但正文抓取需解决 `query.sse.com.cn` 搜索 API 参数或浏览器 403。
- 北交所、上期所、能源中心、大商所、广期所存在 WAF/JS challenge 或证书问题。
- 中债登业务规则目录已确认，详情正文未核验。

## Lane D：金监总局 / 上位法 / 数据安全等

状态：子 Agent 上下文溢出失败。该 lane 改由主 Agent 后续本地补做。
