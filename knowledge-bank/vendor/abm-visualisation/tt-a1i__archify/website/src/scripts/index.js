
  /* ══════════════════════════════════════
     i18n strings
  ══════════════════════════════════════ */
  const LANGS = {
    en: {
      'label-life':'Beyond code',
      'life-h2':'Not just for code. <em>For anything with steps.</em>',
      'life-body':'Leave plans, job hunts, renting, a monthly budget — each one below is a real Archify artifact, generated and validated exactly like a system diagram. Open one and click around.',
      'life-note':'Numbers in these examples are illustrative. Describe your own situation and your agent draws yours.',
      'life-leave-k':'Workflow',
      'life-leave-q':'How should I spread my leave across the year?',
      'life-job-k':'Lifecycle',
      'life-job-q':'Where does each job application stand?',
      'life-money-k':'Data flow',
      'life-money-q':'Where does my paycheck go each month?',
      'life-rent-k':'Sequence',
      'life-rent-q':'Who says what when I rent a flat?',
      'arch-k':'Architecture',
      'wf-k':'Workflow',
      'seq-k':'Sequence',
      'flow-k':'Data flow',
      'life-k':'Lifecycle',
      'nav-guide':'Guide','nav-gallery':'Proof Lab','nav-start':'Start','nav-community':'Community','nav-install':'Install Skill',
      'hero-badge':"Stable Agent Skill · see what's new",'hero-works':'Works with',
      'hero-h1':'<span class="l">Describe it in plain words.</span><span class="l">Get a map <em>you can trust.</em></span>',
      'hero-sub':'A leave plan, a job hunt, a monthly budget, or a software system — if it has steps, parts, relationships, or states, your AI agent turns it into one explorable HTML map, validated before it ships.',
      'hero-cta':'Get started','hero-stars':'stars on GitHub','copy':'Copy','copied':'Copied',
      'demo-watch':'Watch the 35s demo','demo-title':'Archify 35-second demo','demo-close':'Close demo',
      'tour-title':'Live artifact tour',
      'proof-live':'Live','proof-open':'Open artifact',
      'beat-0-k':'Map','beat-1-k':'Focus','beat-2-k':'Upstream','beat-3-k':'Lens',
      'beat-0-t':'The whole system, in one readable frame.','beat-0-b':'This is the real generated artifact, not a screenshot. Lanes, boundaries, and every authored edge — scroll to move its camera.',
      'beat-1-t':'Focus one node, see what it drives.','beat-1-b':'Press Enter on any node — or open a stable link — and the camera isolates everything downstream of it.',
      'beat-2-t':'Flip the reach. Find the cause.','beat-2-b':'Trace upstream to every dependency that feeds a step. Same file, same authored relationships, one hash change.',
      'beat-3-t':'Compare by meaning, not by box.','beat-3-b':'Lens keeps only the semantic kinds you name — security against data, backend against storage — and quiets the rest.',
      'stat-types':'Diagram types','stat-presets':'Visual presets','stat-checks':'Validation checks per artifact','stat-export':'Native export scale','stat-deps':'Runtime dependencies',
      'label-types':'Diagram types',
      'types-h2':'Five questions. <em>Five kinds of map.</em>',
      'types-body':'Ask the question you actually have. Archify picks the picture that answers it — for a software system, a plan, or something in your own life.',
      'types-more':'Browse the full proof gallery','types-more-sub':'Live artifacts · every preset · every type',
      'arch-h':'What is it made of?',
      'arch-p':'The parts of something and how they connect — a household\'s accounts and cards, a team\'s roles, or a cloud system\'s services, databases, and security boundaries.',
      'arch-li1':'Household accounts','arch-li2':'Team roles','arch-li3':'Microservices topology','arch-li4':'Cloud + security boundaries',
      'wf-h':'What happens next?',
      'wf-p':'Steps across people or stages — a visa application, a leave plan, onboarding, an approval chain, or a CI/CD pipeline, lane by lane.',
      'seq-h':'Who says what, in what order?',
      'seq-p':'Back-and-forth in order — renting a flat through an agent, an expense claim, or an API call chain with its returns.',
      'flow-h':'Where does it all go?',
      'flow-p':'Where something moves and where it lands — a paycheck into bills and savings, documents through review, or data through a pipeline.',
      'life-h':'Where does it stand now?',
      'life-p':'States and what moves between them — job applications, an order, a passport renewal, or a deployment — with waits, retries, and endings.',
      'label-features':'Output',
      'features-h2':'One file. <em>Everything inside.</em>',
      'cmp-light':'Light','cmp-dark':'Dark',
      'fv1-h':'Dual-theme output','fv1-p':"Every diagram ships with coordinated dark and light variable sets. The HTML theme toggle and the SVG @media prefers-color-scheme rule switch together — one file follows the reader's theme.",'fv1-tag':'LIGHT · DARK · ONE FILE',
      'fv2-h':'One menu, every format','fv2-p':'PNG, JPEG, WebP, dual-theme SVG, WebM motion, or straight to the clipboard — every export renders natively in the browser from the same menu.',
      'exp-clip-fmt':'Clipboard',
      'f2-h':'Ultra-crisp 4× export','f2-p':'PNG, JPEG, WebP — all rasterized natively at up to 4× source resolution by the browser. No upsampling blur. Sharp on retina displays, slides, and print.',
      'f5-h':'Self-contained HTML','f5-p':'One HTML file. Zero dependencies, no server, no runtime. Open it in any browser and it works. Share by attaching it to an email or PR comment.',
      'f6-h':'Iterate by chat','f6-p':'"Move the summer trip to August", "add Redis", "make the deadline red" — refine in plain words. No diagram editor to learn.',
      'f7-h':'Inspect and play real routes','f7-p':'Route Journey keeps the complete authored path visible while you inspect any stop or play one finite, reader-controlled pass over each exact incoming relationship.','f7-tag':'INSPECT · PLAY · PAUSE',
      'label-palette':'Design system',
      'palette-h2':'Color that <em>means something.</em>',
      'palette-body':'Seven node colours, consistent in both themes. The legend renames them for your story — Backend can read as Vacation, Security as Rule.',
      'chip-frontend':'Frontend','chip-frontend-use':'Client apps, browsers, mobile, UI',
      'chip-backend':'Backend','chip-backend-use':'Services, APIs, workers, daemons',
      'chip-database':'Database','chip-database-use':'DBs, caches, stores, AI/ML',
      'chip-cloud':'Cloud','chip-cloud-use':'Managed services, infra',
      'chip-security':'Security','chip-security-use':'Auth, secrets, guards',
      'chip-bus':'Message Bus','chip-bus-use':'Kafka, RabbitMQ, SNS',
      'chip-external':'External','chip-external-use':'Users, 3rd parties, generic',
      'label-qs':'Quick start',
      'qs-h2':'Three steps. <em>One command.</em>',
      'qs-body':'One checked Skill for Claude Code, Codex, Cursor, OpenCode, and GitHub Copilot. Pick your agent for the exact command.',
      'term-c1':'# Install globally for your agent','term-c2':'# Or try it once with Codex, no permanent install','term-c3':'# Then just ask',
      'term-ask':'› Use Archify to plan my annual leave: 10 days, plus 2 comp days that expire at the end of June.',
      'step1-h':'Install in one command','step1-p':'Run the command for your agent, or open the <a href="start.html?agent=cursor&amp;type=architecture">agent-aware quick start</a> for project-scoped installs.',
      'step2-h':'Describe your system','step2-p':'Describe the steps, people, parts, or states — or ask your agent to read a repository first.',
      'step3-h':'Ask your agent to draw it','step3-p':'Tell your agent to use Archify. It generates a self-contained HTML file you can open in any browser and refine in chat.',
      'kbd-label':'Inside every artifact','kbd-guide':'Diagram guide','kbd-theme':'Toggle theme','kbd-find':'Find node / route endpoint','kbd-route':'Trace, inspect, and play a route','kbd-radar':'Semantic radar','kbd-lens':'Compare semantic kinds','kbd-present':'Presentation stage','kbd-export':'Open export menu','kbd-focus':'Focus node','kbd-zoom':'Reading depth / reset','kbd-nav':'Navigate menu','kbd-close':'Close menu',
      'footer-meta':'stable &nbsp;·&nbsp; v[[ARCHIFY_VERSION]] &nbsp;·&nbsp; MIT License<br>Based on Cocoon-AI/architecture-diagram-generator',
      'cta-h':'Describe it once.<br><em>Share the map.</em>',
      'cta-sub':'One command installs the checked skill for your agent — and your next diagram is a chat message away.',
      'cta-install':'Install the skill','cta-gh':'Star on GitHub',
      'footer-changelog':'Changelog','footer-license':'License','footer-community':'Community'
    },
    zh: {
      'label-life':'不只是代码',
      'life-h2':'不只是代码，<br><em>生活里的事也能画。</em>',
      'life-body':'年假规划、求职进度、租房沟通、每月收支——下面每一张都是真实生成的 Archify 成品，和系统架构图走同一套生成与校验流程。点开就能探索。',
      'life-note':'示例里的数字仅作演示。描述你自己的情况，Agent 就会画出你的那一张。',
      'life-leave-k':'工作流',
      'life-leave-q':'一年的假怎么排最划算？',
      'life-job-k':'生命周期',
      'life-job-q':'每份求职申请走到哪一步了？',
      'life-money-k':'数据流',
      'life-money-q':'工资每个月都去哪了？',
      'life-rent-k':'时序图',
      'life-rent-q':'租房时，谁跟谁说了什么？',
      'arch-k':'架构图',
      'wf-k':'工作流',
      'seq-k':'时序图',
      'flow-k':'数据流',
      'life-k':'生命周期',
      'nav-guide':'场景指南','nav-gallery':'验证作品集','nav-start':'快速上手','nav-community':'社区包','nav-install':'安装技能',
      'hero-badge':'稳定版 Agent 技能 · 查看更新','hero-works':'支持',
      'hero-h1':'<span class="l">用大白话讲清楚，</span><span class="l">得到<em>一张可信的图。</em></span>',
      'hero-sub':'年假怎么排、求职走到哪步、工资去哪了，或者一整套软件系统——只要它有步骤、组成、关系或状态，你的 AI Agent 都能把它变成一张可以点开探索、交付前已经校验过的 HTML 图。',
      'hero-cta':'开始使用','hero-stars':'GitHub Star','copy':'复制','copied':'已复制',
      'demo-watch':'观看 35 秒演示','demo-title':'Archify 35 秒演示','demo-close':'关闭演示',
      'tour-title':'实时成品导览',
      'proof-live':'实时','proof-open':'打开完整成品',
      'beat-0-k':'全景','beat-1-k':'聚焦','beat-2-k':'上游','beat-3-k':'语义镜头',
      'beat-0-t':'整个系统，一屏读完。','beat-0-b':'这是真实生成的成品，不是截图。泳道、边界和每一条作者连线都在这里——继续滚动，移动它的镜头。',
      'beat-1-t':'聚焦一个节点，看清它驱动了什么。','beat-1-b':'在任意节点上按 Enter，或打开一个稳定链接，镜头会只保留它下游的一切。',
      'beat-2-t':'反转方向，找到源头。','beat-2-b':'向上游追溯，看清喂给这一步的每个依赖。同一个文件、同一组作者关系，只改一次 hash。',
      'beat-3-t':'按语义对比，而不是按方框。','beat-3-b':'语义镜头只保留你点名的类型——安全对数据、后端对存储——其余全部压暗。',
      'stat-types':'图表类型','stat-presets':'视觉预设','stat-checks':'每个成品的校验项','stat-export':'原生导出倍率','stat-deps':'运行时依赖',
      'label-types':'图表类型',
      'types-h2':'五个问题，<br><em>五种图。</em>',
      'types-body':'问你真正想问的问题。Archify 会选出能回答它的那种图——不管是一套软件系统、一份计划，还是你自己生活里的事。',
      'types-more':'浏览完整作品集','types-more-sub':'实时成品 · 全部预设 · 全部图型',
      'arch-h':'它由什么组成？',
      'arch-p':'一件事由哪些部分组成、彼此怎么连接——家里的账户和银行卡、团队分工，或者云上系统的服务、数据库与安全边界。',
      'arch-li1':'家庭账户','arch-li2':'团队分工','arch-li3':'微服务拓扑','arch-li4':'云与安全边界',
      'wf-h':'下一步做什么？',
      'wf-p':'跨人、跨阶段的步骤——办签证、排年假、新人入职、审批链，或者 CI/CD 流水线，逐泳道铺开。',
      'seq-h':'谁先谁后，怎么来回？',
      'seq-p':'按顺序的一来一回——通过中介租房、报销往返，或者带返回值的 API 调用链。',
      'flow-h':'东西都流向哪里？',
      'flow-p':'东西从哪来、最后落到哪——工资流向账单和储蓄、文件流转审阅，或者数据穿过管道。',
      'life-h':'现在走到哪一步了？',
      'life-p':'有哪些状态、怎么在状态之间变化——求职申请、一笔订单、护照换发或一次部署，含等待、重试和结局。',
      'label-features':'输出',
      'features-h2':'一个文件，<br><em>全部都在里面。</em>',
      'cmp-light':'浅色','cmp-dark':'深色',
      'fv1-h':'双主题输出','fv1-p':'每张图都内置协调的深色与浅色变量集：HTML 的主题开关与 SVG 的 @media prefers-color-scheme 规则同步切换——一个文件，自动跟随读者主题。','fv1-tag':'浅色 · 深色 · 单文件',
      'fv2-h':'一个菜单，全部格式','fv2-p':'PNG、JPEG、WebP、双主题 SVG、WebM 动图，或直接复制到剪贴板——所有导出都在浏览器内原生渲染，同一个菜单完成。',
      'exp-clip-fmt':'剪贴板',
      'f2-h':'超清 4× 导出','f2-p':'PNG、JPEG、WebP——由浏览器以最高 4 倍分辨率原生栅格化，无上采样模糊。视网膜屏、幻灯片、印刷均清晰。',
      'f5-h':'独立 HTML 文件','f5-p':'单个 HTML 文件，零依赖、无需服务器或构建工具，任意浏览器打开即用。作为附件发邮件或贴 PR 评论均可。',
      'f6-h':'对话式迭代','f6-p':'「把暑假旅行挪到八月」「加一个 Redis」「把截止日标红」——用大白话精调，不用学任何画图工具。',
      'f7-h':'检查并播放真实路径','f7-p':'Route Journey 始终保留完整作者路径，可逐站检查，也可沿每条精确入向关系播放一次由读者控制的有限旅程。','f7-tag':'检查 · 播放 · 暂停',
      'label-palette':'设计系统',
      'palette-h2':'每种颜色，<br><em>都有含义。</em>',
      'palette-body':'七种节点颜色，深浅主题下保持一致。图例可以按你的故事改名——「后端」可以叫「假期」，「安全」可以叫「规则」。',
      'chip-frontend':'前端','chip-frontend-use':'客户端、浏览器、移动端、UI',
      'chip-backend':'后端','chip-backend-use':'服务、API、Worker、守护进程',
      'chip-database':'数据库','chip-database-use':'数据库、缓存、存储、AI/ML',
      'chip-cloud':'云服务','chip-cloud-use':'托管服务、基础设施',
      'chip-security':'安全','chip-security-use':'鉴权、密钥、安全网关',
      'chip-bus':'消息总线','chip-bus-use':'Kafka、RabbitMQ、SNS',
      'chip-external':'外部系统','chip-external-use':'用户、第三方、通用外部',
      'label-qs':'快速开始',
      'qs-h2':'三步上手，<br><em>一条命令。</em>',
      'qs-body':'同一份经过检查的 Skill 可用于 Claude Code、Codex、Cursor、OpenCode 和 GitHub Copilot。选择你的 Agent，获取准确命令。',
      'term-c1':'# 为你的 Agent 全局安装','term-c2':'# 或者用临时副本在 Codex 中试一次','term-c3':'# 然后直接说',
      'term-ask':'› 用 Archify 帮我排一下今年的年假：10 天年假，加 2 天 6 月底过期的调休。',
      'step1-h':'一条命令安装','step1-p':'运行对应 Agent 的命令，或打开<a href="start.html?agent=cursor&amp;type=architecture">可切换 Agent 的快速开始页</a>获取项目级安装命令。',
      'step2-h':'描述你的系统','step2-p':'描述步骤、角色、组成或状态，也可以先让 agent 读一下代码仓库。',
      'step3-h':'让 agent 绘制','step3-p':'告诉 agent 使用 Archify，它会生成可在任意浏览器打开的单文件 HTML，并可继续在对话中迭代。',
      'kbd-label':'每个成品都内置','kbd-guide':'图表指南','kbd-theme':'切换主题','kbd-find':'查找节点 / 路径端点','kbd-route':'探查、检查并播放路径','kbd-radar':'语义雷达','kbd-lens':'对比语义类型','kbd-present':'演示舞台','kbd-export':'打开导出菜单','kbd-focus':'聚焦节点','kbd-zoom':'阅读层级 / 复位','kbd-nav':'菜单导航','kbd-close':'关闭菜单',
      'footer-meta':'稳定版 &nbsp;·&nbsp; v[[ARCHIFY_VERSION]] &nbsp;·&nbsp; MIT 许可证<br>基于 Cocoon-AI/architecture-diagram-generator',
      'cta-h':'描述一次，<br><em>分享这张图。</em>',
      'cta-sub':'一条命令为你的 Agent 安装经过检查的技能——下一张架构图，只差一句对话。',
      'cta-install':'安装技能','cta-gh':'在 GitHub 上 Star',
      'footer-changelog':'更新日志','footer-license':'许可证','footer-community':'社区包'
    }
  };

  /* The MAP beat clears focus/lens with a fragment that names no element: an
     empty '#' would make the browser scroll the indicated "top of document"
     into view, which in a same-origin frame also scrolls this page. */
  const MAP = '#overview';

  /* Each proof carries four camera beats (focus → upstream → lens → map) that
     the pinned stage applies by replacing the artifact's hash; the viewer
     animates its own camera on hashchange. */
  const PROOFS = {
    signal: {
      artifact: 'gallery/artifacts/agent-tool-call.workflow.html',
      hash: '#focus=planner&reach=downstream',
      beats: [MAP, '#focus=planner&reach=downstream', '#focus=approval&reach=upstream', '#lens=security~database'],
      iframeTitle: { en: 'Agent Tool Call live Archify proof', zh: '智能体工具调用 Archify 实时成品' },
      name: { en: 'Agent Tool Call', zh: '智能体工具调用' },
      meta: { en: 'Workflow · Signal Flow · 12 nodes · 11 edges', zh: '工作流 · Signal Flow · 12 节点 · 11 条关系' },
      title: { en: 'Agent Tool Call — policy, execution, recovery, and evidence', zh: '智能体工具调用——策略、执行、恢复与证据闭环' }
    },
    blueprint: {
      artifact: 'gallery/artifacts/production-deployment.architecture.html',
      hash: '#lens=backend~database',
      beats: [MAP, '#focus=gateway&reach=downstream', '#focus=postgres&reach=upstream', '#lens=backend~database'],
      iframeTitle: { en: 'Production Deployment live Archify proof', zh: '生产部署架构 Archify 实时成品' },
      name: { en: 'Production Deployment', zh: '生产部署' },
      meta: { en: 'Architecture · Blueprint · 12 nodes · 12 edges', zh: '架构图 · Blueprint · 12 节点 · 12 条关系' },
      title: { en: 'Production Deployment — regions, ownership, state, and audit', zh: '生产部署——区域、归属、状态与审计边界' }
    },
    leave: {
      artifact: 'cases/life/leave-plan.workflow.html',
      hash: '#focus=spring&reach=downstream',
      beats: [MAP, '#focus=spring&reach=downstream', '#focus=done&reach=upstream', '#lens=backend~security'],
      iframeTitle: { en: 'Annual leave plan live Archify artifact', zh: '年假规划 Archify 实时成品' },
      name: { en: 'Annual Leave', zh: '年假规划' },
      meta: { en: 'Workflow · Classic · 8 nodes · 7 edges', zh: '工作流 · Classic · 8 节点 · 7 条关系' },
      title: { en: 'Annual leave — four breaks, two rules, zero days wasted', zh: '一年的年假——四次拼假、两条规则、一天不浪费' }
    },
    classic: {
      artifact: 'gallery/artifacts/cache-miss.sequence.html',
      hash: '#route=web~db',
      embedHash: '#focus=web&reach=downstream',
      beats: [MAP, '#focus=web&reach=downstream', '#focus=db&reach=upstream', '#lens=database~security'],
      iframeTitle: { en: 'Cache Miss Request live Archify proof', zh: '缓存未命中请求 Archify 实时成品' },
      name: { en: 'Cache Miss', zh: '缓存未命中' },
      meta: { en: 'Sequence · Classic · 7 participants · 12 messages', zh: '时序图 · Classic · 7 个参与者 · 12 条消息' },
      title: { en: 'Cache Miss — authentication, fallback, return, and trace', zh: '缓存未命中——鉴权、回退、返回与追踪' }
    }
  };

  let lang = ArchifySiteLanguage.read();
  let activeProof = 'signal';
  let beat = 0;
  const $ = id => document.getElementById(id);
  const btnLang = $('btn-lang');
  const proofStage = $('hero-proof-stage');
  const proofFrame = $('hero-proof-frame');
  const proofPanel = $('hero-proof-panel');
  const proofOpen = $('proof-open');
  const proofMeta = $('proof-meta');
  const proofTitle = $('proof-title');
  const addressFile = $('address-file');
  const addressHash = $('address-hash');
  const beatCard = document.querySelector('.beat-card');
  const beatTicks = [...document.querySelectorAll('.beat-tick')];

  const siteTheme = () => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  /* the artifact is same-origin, so its own theme attribute follows the site */
  function syncFrameTheme() {
    try { proofFrame.contentDocument.documentElement.setAttribute('data-theme', siteTheme()); } catch (_) {}
  }
  window.addEventListener('archify:themechange', syncFrameTheme);

  function proofEmbedUrl(proof) {
    return `${proof.artifact}?embed=1&theme=${siteTheme()}${proof.embedHash || proof.hash}`;
  }

  function replaceFrameHash(hash) {
    try {
      const loc = proofFrame.contentWindow.location;
      if (loc.protocol === 'about:' || loc.hash === hash) return;
      loc.replace(loc.pathname + loc.search + hash);
    } catch (_) {}
  }

  function renderBeat(next, { apply = true } = {}) {
    const proof = PROOFS[activeProof];
    const hash = proof.beats[next];
    const changed = next !== beat;
    beat = next;
    beatTicks.forEach((tick, i) => tick.setAttribute('aria-pressed', String(i === next)));
    $('beat-title').textContent = LANGS[lang][`beat-${next}-t`];
    $('beat-body').textContent = LANGS[lang][`beat-${next}-b`];
    addressHash.textContent = hash === MAP ? '' : hash;
    if (changed) {
      beatCard.classList.remove('is-swapping'); void beatCard.offsetWidth; beatCard.classList.add('is-swapping');
      addressHash.classList.remove('is-flash'); void addressHash.offsetWidth; addressHash.classList.add('is-flash');
    }
    if (apply && changed) replaceFrameHash(hash);
  }

  function renderProof(key, { focus = false } = {}) {
    const proof = PROOFS[key];
    if (!proof) return;
    activeProof = key;
    document.querySelectorAll('.spec-card').forEach(tab => {
      const selected = tab.dataset.proof === key;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      tab.querySelector('.spec-name').textContent = PROOFS[tab.dataset.proof].name[lang];
      if (selected && focus) tab.focus();
    });
    proofPanel.setAttribute('aria-labelledby', `proof-tab-${key}`);
    proofOpen.href = `${proof.artifact}?present=1${proof.hash}`;
    proofMeta.textContent = proof.meta[lang];
    proofTitle.textContent = proof.title[lang];
    proofFrame.title = proof.iframeTitle[lang];
    addressFile.textContent = proof.artifact.split('/').pop();
    if (proofFrame.dataset.proof !== key) {
      proofStage.classList.add('is-loading');
      proofFrame.dataset.proof = key;
      proofFrame.src = proofEmbedUrl(proof);
    }
    renderBeat(beat, { apply: false });
  }

  proofFrame.addEventListener('load', () => {
    proofStage.classList.remove('is-loading');
    syncFrameTheme();
    replaceFrameHash(PROOFS[activeProof].beats[beat]);
  });
  document.querySelectorAll('.spec-card').forEach(tab => {
    tab.addEventListener('click', () => renderProof(tab.dataset.proof));
    tab.addEventListener('keydown', event => {
      const tabs = [...document.querySelectorAll('.spec-card')];
      const current = tabs.indexOf(tab);
      let next = current;
      if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      renderProof(tabs[next].dataset.proof, { focus: true });
    });
  });

  function applyLang(l) {
    lang = ArchifySiteLanguage.write(l);
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    btnLang.textContent = lang === 'zh' ? 'EN' : '中文';
    btnLang.setAttribute('aria-label', lang === 'zh' ? 'Switch to English' : '切换到中文');
    const dict = LANGS[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const v = dict[el.dataset.i18n];
      if (v !== undefined) el.innerHTML = v;
    });
    renderProof(activeProof);
  }

  btnLang.addEventListener('click', () => applyLang(lang === 'en' ? 'zh' : 'en'));
  applyLang(lang);

  /* ══ Reveal on enter ══ */
  if ('IntersectionObserver' in window) {
    const obs = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); } });
    }, { threshold:.12, rootMargin:'0px 0px -40px 0px' });
    document.querySelectorAll('.fade-up').forEach(el => obs.observe(el));
  } else {
    document.querySelectorAll('.fade-up').forEach(el => el.classList.add('visible'));
  }

  /* ══ Stage orchestration — window flattens as it arrives, then the pinned
     scroll distance is split into four camera beats ══ */
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const stage = $('tour');
  const BEATS = beatTicks.length;

  function stageProgress() {
    const rect = stage.getBoundingClientRect();
    const vh = window.innerHeight;
    const enter = Math.min(1, Math.max(0, 1 - rect.top / (vh * 0.9)));
    const travel = Math.max(1, rect.height - vh);
    const pinned = Math.min(1, Math.max(0, -rect.top / travel));
    return { enter, pinned, rect, travel };
  }

  function applyScroll() {
    const { enter, pinned } = stageProgress();
    if (!reducedMotion.matches) stage.style.setProperty('--enter', enter.toFixed(3));
    const span = pinned * BEATS;
    const next = Math.min(BEATS - 1, Math.floor(span));
    beatTicks.forEach((tick, i) => tick.style.setProperty('--fill', `${Math.round(Math.min(1, Math.max(0, span - i)) * 100)}%`));
    if (next !== beat) renderBeat(next);
  }

  beatTicks.forEach((tick, i) => tick.addEventListener('click', () => {
    const { rect, travel } = stageProgress();
    const top = window.scrollY + rect.top + travel * ((i + 0.5) / BEATS);
    window.scrollTo({ top, behavior: reducedMotion.matches ? 'auto' : 'smooth' });
  }));

  let scrollTick = false;
  const onScroll = () => {
    if (scrollTick) return;
    scrollTick = true;
    requestAnimationFrame(() => { scrollTick = false; applyScroll(); });
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  applyScroll();

  /* ══ Hero pointer spotlight — fine pointers only, never under reduced motion ══ */
  const hero = document.querySelector('.hero');
  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches && !reducedMotion.matches) {
    let spotTick = false, spotX = 0, spotY = 0;
    hero.addEventListener('pointermove', event => {
      spotX = event.clientX; spotY = event.clientY;
      if (spotTick) return;
      spotTick = true;
      requestAnimationFrame(() => {
        spotTick = false;
        const rect = hero.getBoundingClientRect();
        hero.style.setProperty('--mx', `${spotX - rect.left}px`);
        hero.style.setProperty('--my', `${spotY - rect.top}px`);
        hero.classList.add('is-pointing');
      });
    });
    hero.addEventListener('pointerleave', () => hero.classList.remove('is-pointing'));
  }

  /* ══ Diagram types — index list drives the preview plate ══ */
  const typeItems = [...document.querySelectorAll('.type-item')];
  const typeImgs = [...document.querySelectorAll('.type-plate img')];
  function selectType(key) {
    typeItems.forEach(item => {
      const on = item.dataset.type === key;
      item.classList.toggle('is-active', on);
      item.querySelector('button').setAttribute('aria-pressed', String(on));
    });
    typeImgs.forEach(img => img.classList.toggle('is-active', img.dataset.type === key));
  }
  typeItems.forEach(item => {
    const button = item.querySelector('button');
    button.addEventListener('click', () => selectType(item.dataset.type));
    button.addEventListener('mouseenter', () => { if (window.matchMedia('(hover: hover)').matches) selectType(item.dataset.type); });
  });

  /* ══ Light/dark compare ══ */
  const compareStage = $('compare-stage');
  $('compare-range').addEventListener('input', event => compareStage.style.setProperty('--split', `${event.target.value}%`));

  /* ══ Agent command switcher ══ */
  const agentCommand = $('agent-command');
  const agentTabs = [...document.querySelectorAll('.agent-tabs button')];
  function selectAgent(tab, focus) {
    agentTabs.forEach(t => { const on = t === tab; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; });
    agentCommand.textContent = `npx -y skills add tt-a1i/archify --skill archify --agent ${tab.dataset.agent} --global --copy --yes`;
    if (focus) tab.focus();
  }
  agentTabs.forEach((tab, i) => {
    tab.addEventListener('click', () => selectAgent(tab));
    tab.addEventListener('keydown', event => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      selectAgent(agentTabs[(i + step + agentTabs.length) % agentTabs.length], true);
    });
  });

  /* ══ Copy buttons ══ */
  document.querySelectorAll('.cmd-copy').forEach(button => button.addEventListener('click', async () => {
    const text = button.dataset.copyText || $(button.dataset.copyFrom).textContent;
    try { await navigator.clipboard.writeText(text); } catch (_) { return; }
    const label = button.querySelector('.cmd-copy-label');
    button.classList.add('is-copied');
    label.textContent = LANGS[lang].copied;
    setTimeout(() => { button.classList.remove('is-copied'); label.textContent = LANGS[lang].copy; }, 1600);
  }));

  /* ══ Demo lightbox — zero network cost until the trigger is pressed ══ */
  const DEMO_SRC = 'https://github.com/user-attachments/assets/78570807-ba1d-4737-953f-55504a378a87';
  const demoOpen = $('demo-open');
  const demoDialog = $('demo-dialog');
  const demoVideo = $('demo-video');

  demoOpen.addEventListener('click', () => {
    demoVideo.src = DEMO_SRC;
    document.documentElement.classList.add('demo-lock');
    demoDialog.showModal();
    demoVideo.play().catch(() => {});
  });
  $('demo-close').addEventListener('click', () => demoDialog.close());
  demoDialog.addEventListener('click', event => {
    if (event.target === demoDialog) demoDialog.close();
  });
  demoDialog.addEventListener('close', () => {
    demoVideo.pause();
    demoVideo.removeAttribute('src');
    demoVideo.load();
    document.documentElement.classList.remove('demo-lock');
    demoOpen.focus();
  });
