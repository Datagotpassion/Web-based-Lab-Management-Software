/* Interface translation.
 *
 * Applied to the rendered page rather than the templates. Most of this
 * interface is built in JavaScript -- the freezer map, the structure editor,
 * the antibody tables -- so wrapping template text alone would leave the
 * majority untranslated.
 *
 * Only text that matches a dictionary entry exactly is replaced, so lab data
 * is never touched: a reagent called "Shelf 2" is not an interface string and
 * will not match. Anything inside [data-no-i18n] is skipped outright.
 *
 * Adding a language: add its code to LANGUAGES and a column to each entry.
 */

const I18N_LANGUAGES = {en: 'English', zh: '中文'};

const I18N = {
  // ---- navigation and chrome
  'Lab Management System': {zh: '实验室管理系统'},
  'Home': {zh: '主页'},
  'Structure': {zh: '存储结构'},
  'Antibodies': {zh: '抗体'},
  'Calculators': {zh: '计算器'},
  'Import/Export': {zh: '导入/导出'},
  'Dilution Calculator': {zh: '稀释计算器'},
  'Actual Concentration Calculator': {zh: '实际浓度计算器'},
  'Import & Export Data': {zh: '导入与导出数据'},
  'Quick Export CSV': {zh: '快速导出 CSV'},
  'Browser capture setup': {zh: '浏览器抓取设置'},
  'History & undelete': {zh: '历史记录与恢复'},
  'Settings': {zh: '设置'},
  'Save': {zh: '保存'},
  'Cancel': {zh: '取消'},
  'Close': {zh: '关闭'},
  'Delete': {zh: '删除'},
  'Edit': {zh: '编辑'},
  'Back': {zh: '返回'},
  'Loading…': {zh: '加载中…'},
  'Loading...': {zh: '加载中…'},

  // ---- home page
  'Inventory Records': {zh: '库存记录'},
  'Add New Record': {zh: '添加新记录'},
  'Refresh': {zh: '刷新'},
  'Search by name, supplier, or notes...': {zh: '按名称、供应商或备注搜索…'},
  'All Temperatures': {zh: '所有温度'},
  'Room Temperature': {zh: '室温'},
  'ID': {zh: '编号'},
  'Drug Name': {zh: '试剂名称'},
  'Concentration': {zh: '浓度'},
  'Storage': {zh: '存放温度'},
  'Location': {zh: '位置'},
  'Supplier': {zh: '供应商'},
  'Actions': {zh: '操作'},
  'Storage Structure': {zh: '存储结构'},
  'Select All': {zh: '全选'},

  // ---- record form
  'Add New Record ': {zh: '添加新记录'},
  'Edit Record': {zh: '编辑记录'},
  'Save Record': {zh: '保存记录'},
  'Drug Name *': {zh: '试剂名称 *'},
  'Stock Conc.': {zh: '储备浓度'},
  'Unit': {zh: '单位'},
  'Aliquot': {zh: '分装量'},
  'Storage Temperature': {zh: '存放温度'},
  'Preparation Date': {zh: '配制日期'},
  'Lot Number': {zh: '批号'},
  'Product Number': {zh: '货号'},
  'Sterility': {zh: '无菌性'},
  'Light Sensitive': {zh: '避光'},
  'Solvents': {zh: '溶剂'},
  'Solubility': {zh: '溶解性'},
  'Preparation Time': {zh: '配制时间'},
  'Expiration Time': {zh: '有效期'},
  'Storage Location': {zh: '存放位置'},
  'Notes': {zh: '备注'},
  'Not Specified': {zh: '未指定'},
  'Sterile': {zh: '无菌'},
  'Non-sterile': {zh: '非无菌'},
  'Yes': {zh: '是'},
  'No': {zh: '否'},
  'No location set': {zh: '未设置位置'},
  'Items at Location': {zh: '该位置的物品'},

  // ---- supplier lookup
  "Paste the supplier's product page, then Fetch":
      {zh: '粘贴供应商产品页面网址，然后点击获取'},
  'Fetch details': {zh: '获取详情'},
  'From browser': {zh: '从浏览器获取'},
  'Use pasted page': {zh: '使用粘贴的页面'},
  'On the product page press Ctrl+A then Ctrl+C, and paste here':
      {zh: '在产品页面按 Ctrl+A 再按 Ctrl+C，粘贴到此处'},
  'Reading the supplier page…': {zh: '正在读取供应商页面…'},
  'Reading the captured page…': {zh: '正在读取已抓取的页面…'},
  'Nothing new to fill.': {zh: '没有可填充的新内容。'},
  'Paste the product page address first.': {zh: '请先粘贴产品页面网址。'},
  'Paste the page contents first.': {zh: '请先粘贴页面内容。'},

  // ---- storage structure / freezer map
  'Freezer Map': {zh: '冰箱布局图'},
  'Front view': {zh: '正视图'},
  'Edit layout': {zh: '编辑布局'},
  'Tree editor': {zh: '树状编辑器'},
  'Units': {zh: '设备'},
  'Add Unit': {zh: '添加设备'},
  'Add inside': {zh: '在此添加'},
  'Container properties': {zh: '容器属性'},
  'Label': {zh: '名称'},
  'Kind': {zh: '类型'},
  'Name': {zh: '名称'},
  'Room': {zh: '房间'},
  'Owning lab': {zh: '所属实验室'},
  'How many': {zh: '数量'},
  'Label as': {zh: '编号方式'},
  'Prefix': {zh: '前缀'},
  'Add': {zh: '添加'},
  'Select a unit': {zh: '请选择一台设备'},
  'Expand': {zh: '展开'},
  'Collapse': {zh: '收起'},
  'Unplaced items': {zh: '未放置的物品'},
  'Pick a box to see what is in it.': {zh: '点击一个盒子查看其内容。'},
  'Nothing stored here.': {zh: '此处没有存放物品。'},
  'Empty.': {zh: '空。'},
  'Edit contents': {zh: '编辑内容'},
  'Save contents': {zh: '保存内容'},
  'Filter by name…': {zh: '按名称筛选…'},
  'Unplaced only': {zh: '仅显示未放置'},
  'Within a rack, positions run left to right then down, with the door edge on the right.':
      {zh: '在同一个架子内，位置从左到右、从上到下编号，右侧为冰箱门一侧。'},
  'Click a position to say what is stored there. Numbered left to right, door on the right.':
      {zh: '点击某个位置以填写存放内容。编号从左到右，右侧为门一侧。'},
  'What is in here is listed first. Tick to add, untick to remove — removing clears an item’s location rather than deleting it.':
      {zh: '当前存放的物品排在最前。勾选以添加，取消勾选以移除——移除只会清除位置，不会删除记录。'},

  // ---- history
  'History': {zh: '历史记录'},
  'Recent changes': {zh: '最近的更改'},
  'Deleted — restorable': {zh: '已删除——可恢复'},
  'Put back': {zh: '恢复'},
  'All records': {zh: '所有记录'},
  'Reagents': {zh: '试剂'},
  'Primary antibodies': {zh: '一抗'},
  'Secondary antibodies': {zh: '二抗'},
  'Every change to a record, and what can be put back.':
      {zh: '每条记录的更改，以及可以恢复的内容。'},
  'No changes recorded yet.': {zh: '尚无更改记录。'},
  'Nothing deleted.': {zh: '没有已删除的记录。'},
  'created': {zh: '已创建'},
  'deleted': {zh: '已删除'},
  'updated': {zh: '已更新'},
  'create': {zh: '创建'},
  'update': {zh: '更新'},
  'delete': {zh: '删除'},

  // ---- the freezer-side display
  'Find a reagent': {zh: '查找试剂'},
  'Browse the freezer': {zh: '浏览冰箱'},
  'shelves and racks': {zh: '层架与架子'},
  'Previous': {zh: '上一页'},
  'More': {zh: '下一页'},
  'Back to list': {zh: '返回列表'},
  'Nothing here.': {zh: '此处为空。'},
  'highlighted below': {zh: '已在下方高亮'},
  'no network': {zh: '无网络'},
  'synced': {zh: '已同步'},
  'Could not reach the server.': {zh: '无法连接服务器。'},

  // ---- import/export
  'Export': {zh: '导出'},
  'Import': {zh: '导入'},
  'Download CSV': {zh: '下载 CSV'},
  'Choose File': {zh: '选择文件'},

  // ---- antibodies
  'Primary Antibodies': {zh: '一抗'},
  'Secondary Antibodies': {zh: '二抗'},
  'Panel Matcher': {zh: '组合搭配'},
  'Target Protein': {zh: '靶蛋白'},
  'Host Species': {zh: '宿主种属'},
  'Clonality': {zh: '单/多克隆'},
  'Isotype': {zh: '亚型'},
  'Clone Number': {zh: '克隆号'},
  'Catalog Number': {zh: '货号'},
  'Applications': {zh: '应用'},
  'Fluorophore': {zh: '荧光基团'},
  'Conjugate': {zh: '偶联物'},
  'Target Species': {zh: '靶种属'},
  'Cross-adsorbed': {zh: '交叉吸附'},
  'Monoclonal': {zh: '单克隆'},
  'Polyclonal': {zh: '多克隆'},
  'Fluorophore conflict': {zh: '荧光基团冲突'},
  'Cross-reactivity': {zh: '交叉反应'},

  // ---- read-only display notice
  'Read-only display. This is a copy of the lab PC database; add or edit records there.':
      {zh: '只读显示。此处为实验室电脑数据库的副本；请在电脑上添加或修改记录。'},
};

function i18nLang() {
  try {
    return localStorage.getItem('labmgmt-lang') || 'en';
  } catch (e) {
    return 'en';
  }
}

function i18nSetLang(lang) {
  try { localStorage.setItem('labmgmt-lang', lang); } catch (e) { /* private mode */ }
  // A cookie too, so the server could use it later for page titles.
  document.cookie = `lang=${lang};path=/;max-age=31536000`;
  location.reload();
}

function i18nLookup(text, lang) {
  const entry = I18N[text.trim()];
  return entry && entry[lang] ? entry[lang] : null;
}

/* Walk the document replacing exact matches. Safe to call repeatedly, which
 * matters because most views re-render themselves after every change. */
function applyTranslations(root) {
  const lang = i18nLang();
  if (lang === 'en') return;
  const scope = root || document.body;
  if (!scope) return;

  const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest('[data-no-i18n]')) return NodeFilter.FILTER_REJECT;
      if (['SCRIPT', 'STYLE', 'TEXTAREA'].includes(parent.tagName))
        return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const pending = [];
  let node;
  while ((node = walker.nextNode())) pending.push(node);
  pending.forEach(n => {
    const hit = i18nLookup(n.nodeValue, lang);
    if (hit) n.nodeValue = n.nodeValue.replace(n.nodeValue.trim(), hit);
  });

  // Attributes the user reads.
  scope.querySelectorAll('[placeholder], [title]').forEach(el => {
    if (el.closest('[data-no-i18n]')) return;
    ['placeholder', 'title'].forEach(attr => {
      const value = el.getAttribute(attr);
      if (!value) return;
      const hit = i18nLookup(value, lang);
      if (hit) el.setAttribute(attr, hit);
    });
  });

  if (document.title) {
    const hit = i18nLookup(document.title, lang);
    if (hit) document.title = hit;
  }
}

/* Re-apply after anything re-renders. A MutationObserver keeps dynamically
 * built views -- which is most of them -- translated without each one having
 * to remember to ask. */
function i18nWatch() {
  if (i18nLang() === 'en') return;
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; applyTranslations(); });
  }).observe(document.body, {childList: true, subtree: true});
}

document.addEventListener('DOMContentLoaded', () => {
  applyTranslations();
  i18nWatch();
});
