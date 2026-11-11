/* Factor payment editor v2: Persian (Jalali) calendar UI, Gregorian UTC persisted dates. */
(function () {
  'use strict';

  // Calendar conversion algorithm (jalaali-js, MIT). All calculations are date-only / UTC.
  const breaks = [-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
  const div = (a,b) => Math.trunc(a / b);
  const mod = (a,b) => a - div(a,b) * b;
  function jalCal(jy) {
    let bl = breaks.length, gy = jy + 621, leapJ = -14, jp = breaks[0], jump = 0;
    if (jy < jp || jy >= breaks[bl-1]) throw new Error('سال شمسی نامعتبر است');
    for (let i=1; i<bl; ++i) {
      const jm = breaks[i]; jump = jm - jp;
      if (jy < jm) break;
      leapJ += div(jump,33)*8 + div(mod(jump,33),4); jp=jm;
    }
    let n = jy - jp;
    leapJ += div(n,33)*8 + div(mod(n,33)+3,4);
    if (mod(jump,33)===4 && jump-n===4) leapJ++;
    const leapG = div(gy,4)-div((div(gy,100)+1)*3,4)-150;
    const march = 20+leapJ-leapG;
    if (jump-n<6) n = n-jump+div(jump+4,33)*33;
    let leap = mod(mod(n+1,33)-1,4);
    if (leap===-1) leap=4;
    return {leap,gy,march};
  }
  function g2d(gy,gm,gd) {
    let d=div((gy+div(gm-8,6)+100100)*1461,4)+div(153*mod(gm+9,12)+2,5)+gd-34840408;
    d=d-div(div(gy+100100+div(gm-8,6),100)*3,4)+752;
    return d;
  }
  function d2g(jdn) {
    let j=4*jdn+139361631;
    j=j+div(div(4*jdn+183187720,146097)*3,4)*4-3908;
    let i=div(mod(j,1461),4)*5+308;
    let gd=div(mod(i,153),5)+1;
    let gm=mod(div(i,153),12)+1;
    let gy=div(j,1461)-100100+div(8-gm,6);
    return {gy,gm,gd};
  }
  function j2d(jy,jm,jd) {
    const r=jalCal(jy);
    return g2d(r.gy,3,r.march)+(jm-1)*31-div(jm,7)*(jm-7)+jd-1;
  }
  function d2j(jdn) {
    const gy=d2g(jdn).gy;
    let jy=gy-621, r=jalCal(jy), k=jdn-g2d(gy,3,r.march);
    if(k>=0) {
      if(k<=185) return {jy,jm:1+div(k,31),jd:mod(k,31)+1};
      k-=186;
    } else {
      jy--; k+=179;
      if(r.leap===1) k++;
    }
    return {jy,jm:7+div(k,30),jd:mod(k,30)+1};
  }
  const toJ = (gy,gm,gd) => d2j(g2d(gy,gm,gd));
  const toG = (jy,jm,jd) => d2g(j2d(jy,jm,jd));
  const monthLength = (jy,jm) => jm<=6 ? 31 : (jm<=11 || jalCal(jy).leap===0 ? 30 : 29);
  const pad = n => String(n).padStart(2,'0');
  const monthsFa = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const weekdays = ['ش','ی','د','س','چ','پ','ج'];
  const normalizeDigits = text => String(text ?? '').replace(/[۰-۹]/g, c=>String(c.charCodeAt(0)-1776))
    .replace(/[٠-٩]/g, c=>String(c.charCodeAt(0)-1632)).replace('٫','.').trim();
  const escaping = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const validGregorian = (v) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
    const [y,m,d]=v.split('-').map(Number);
    const date=new Date(Date.UTC(y,m-1,d));
    return date.getUTCFullYear()===y && date.getUTCMonth()===m-1 && date.getUTCDate()===d;
  };
  function ymdFromStored(value) {
    if (!value || typeof value!=='string') return '';
    const match=value.match(/^(\d{4}-\d{2}-\d{2})(?:[ T]|$)/);
    return match && validGregorian(match[1]) ? match[1] : '';
  }
  function jalaliDisplay(gDate) {
    if(!validGregorian(gDate)) return '';
    const [gy,gm,gd]=gDate.split('-').map(Number), j=toJ(gy,gm,gd);
    return `${j.jy}/${pad(j.jm)}/${pad(j.jd)}`;
  }
  function gregorianFromJalali(jy,jm,jd) {
    if(jy<1200 || jy>1700 || jm<1 || jm>12 || jd<1 || jd>monthLength(jy,jm)) throw new Error('تاریخ شمسی نامعتبر');
    const g=toG(jy,jm,jd);
    return `${g.gy}-${pad(g.gm)}-${pad(g.gd)}`;
  }
  function toStoredDate(gDate,previousValue) {
    if (!gDate) return null;
    // Preserve the historical UTC time component when just the calendar day changes.
    const match=typeof previousValue==='string' && previousValue.match(/^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T]([0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?)(?:Z|\+00(?::00)?)$/);
    return `${gDate} ${match ? match[1] : '00:00:00'}+00`;
  }
  function percentToFraction(v) {
    const n=Number(normalizeDigits(v));
    if(!Number.isFinite(n) || n<=0 || n>100) throw new Error('درصد باید بزرگ‌تر از صفر و حداکثر ۱۰۰ باشد.');
    return String(Number((n/100).toFixed(8)));
  }
  function fractionToPercent(v) {
    if(v===undefined || v===null || v==='') return '';
    return String(Number((Number(normalizeDigits(v))*100).toFixed(8)));
  }
  const selectOptions=(items,current)=>items.map(([v,title])=>`<option value="${v}"${current===v?' selected':''}>${escaping(title)}</option>`).join('');

  function init() {
    const root=document.getElementById('sac-root');
    const details=root && root.querySelector('#sac-details');
    const blob=document.getElementById('sac-initial-data');
    if(!root||!blob||root.dataset.sacInit==='1')return;
    root.dataset.sacInit='1';
    const editable=root.dataset.editable==='1';
    const initiallyMulti=root.dataset.initialMulti==='1';
    const form=root.closest('form')||document.getElementById('main-form');
    const rows=root.querySelector('#sac-rows');
    const error=root.querySelector('#sac-error');
    const summary=root.querySelector('#sac-summary');
    const overview=root.querySelector('#sac-collapsed-summary');
    const addBtn=root.querySelector('#sac-add');
    const addBottom=root.querySelector('#sac-add-bottom');
    const cashRow=root.querySelector('#sac-system-row');
    const totalText=root.querySelector('#sac-base-total');
    const cashAmount=cashRow.querySelector('[data-sac-system="amount"]');
    const cashPercent=cashRow.querySelector('[data-sac-system="percent"]');
    const saleType=form && form.querySelector('select[name="sale_type"]');
    const originalSaleType=saleType ? saleType.value : null;
    const documentType=root.dataset.documentType;
    const documentId=root.dataset.documentId;
    const totalSelector=documentType==='quotation'?'.quotation_total_price':'.factor_total_price';
    const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
    let conditions;
    try {
      conditions=JSON.parse(blob.textContent||'[]');
      if(typeof conditions==='string')conditions=JSON.parse(conditions||'[]');
      if(conditions==null)conditions=[];
      if(!Array.isArray(conditions))throw new Error('not an array');
    }catch(_){conditions=null;}
    let initialManual=conditions===null?[]:conditions.filter(item=>!(item&&item.is_system===true));
    let initialSystem=conditions===null?null:(conditions.find(item=>item&&item.is_system===true)||null);
    const decimal=v=>{const t=normalizeDigits(v).replace(/[٬,،\s\u00a0]/g,'').replace(/[^0-9.+\-]/g,'');if(t==='')return NaN;return Number(t);};
    const fixed=(x,d=8)=>String(Number(Number(x).toFixed(d)));
    const displayMoney=v=>Number.isFinite(v)?nf.format(v):'—';
    const moneyValue=x=>fixed(x,2);

    // v8-safe: grouping is display-only. Numeric JSON remains separator-free.
    function formatPaymentAmount(raw){
      let text=normalizeDigits(raw).replace(/[٬,،\s\u00a0]/g,'');
      const negative=text.startsWith('-')?'-':'';
      text=text.replace(/-/g,'').replace(/[^0-9.]/g,'');
      const dot=text.indexOf('.');
      const integer=(dot<0?text:text.slice(0,dot)).replace(/\B(?=(\d{3})+(?!\d))/g,',');
      const decimals=dot<0?'':'.'+text.slice(dot+1).replace(/\./g,'');
      return negative+integer+decimals;
    }
    function groupAmountInPlace(input){
      const before=input.value;
      const caret=input.selectionStart==null?before.length:input.selectionStart;
      const grouped=formatPaymentAmount(before);
      if(before===grouped)return;
      const newCaret=formatPaymentAmount(before.slice(0,caret)).length;
      input.value=grouped;
      try{input.setSelectionRange(newCaret,newCaret);}catch(_){/* readonly */}
    }
    const isMulti=()=>{
      if(!saleType)return initiallyMulti;
      if(!saleType.value)return false;
      const sel=saleType.selectedOptions && saleType.selectedOptions[0];
      const title=String(sel?sel.textContent:'').replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/\s+/g,'');
      return title.includes('چندشرطی')||(initiallyMulti&&saleType.value===originalSaleType);
    };
    function toggleVisibility(){root.hidden=!isMulti();if(root.hidden)closeCalendar();else scheduleSync();}
    function showError(msg){error.textContent=msg||'';error.hidden=!msg;if(msg&&details)details.open=true;}
    function hiddenInputs(){return form?Array.from(form.querySelectorAll('input[name="sale_type_multi_condition"]')):[];}
    function invoiceTotal(){
      const els=Array.from(document.querySelectorAll(totalSelector));
      const active=els.find(el=>el.offsetParent!==null)||els[0];
      const raw=active?decimal(('value' in active?active.value:active.textContent)||''):NaN;
      return Number.isFinite(raw)?Math.max(0,raw):0;
    }
    let openCal=null;
    function closeCalendar() {
      if(openCal){openCal.hidden=true;openCal=null;}
    }
    document.addEventListener('click', event=>{
      if(openCal && !openCal.contains(event.target) && !(openCal._anchorWrap && openCal._anchorWrap.contains(event.target))) closeCalendar();
    });
    document.addEventListener('keydown', event=>{if(event.key==='Escape')closeCalendar();});

    function attachCalendar(card,input,field) {
      const wrap=input.closest('.sac-date-wrap');
      const popup=wrap.querySelector('.sac-cal');
      const clear=wrap.querySelector('.sac-date-clear');
      // Render the popup outside the horizontally scrollable single-line rows.
      // Otherwise calendar days can get clipped by the row's overflow container.
      popup._anchorWrap=wrap;
      input._sacPopup=popup;
      document.body.appendChild(popup);
      function positionCalendar(){
        if(popup.hidden)return;
        const rect=input.getBoundingClientRect();
        const width=popup.offsetWidth||285;
        const height=popup.offsetHeight||320;
        const left=Math.max(8,Math.min(window.innerWidth-width-8,rect.right-width));
        const below=rect.bottom+5;
        const top=below+height>window.innerHeight-8 ? Math.max(8,rect.top-height-5):below;
        popup.style.left=left+'px'; popup.style.top=top+'px';
      }
      window.addEventListener('resize',positionCalendar);
      window.addEventListener('scroll',()=>{if(openCal===popup)positionCalendar();},true);
      // Without this, redrawing the month header detaches the clicked button,
      // and the document-level outside-click handler closes the popup.
      popup.addEventListener('click',event=>event.stopPropagation());
      let jView;
      function render() {
        const chosen=input.dataset.gdate;
        popup.innerHTML='';
        const header=document.createElement('div');header.className='sac-cal-head';
        // In RTL layout: previous month on the right (→), next month on the left (←).
        const previous=document.createElement('button');previous.type='button';previous.className='sac-month-prev';previous.textContent='→';previous.setAttribute('aria-label','ماه قبل');previous.title='ماه قبل';
        const next=document.createElement('button');next.type='button';next.className='sac-month-next';next.textContent='←';next.setAttribute('aria-label','ماه بعد');next.title='ماه بعد';
        const heading=document.createElement('div');heading.className='sac-cal-month-picker';
        const monthSelect=document.createElement('select');monthSelect.className='sac-cal-select sac-cal-select-month';monthSelect.setAttribute('aria-label','انتخاب ماه شمسی');
        monthsFa.forEach((name,idx)=>{const opt=document.createElement('option');opt.value=String(idx+1);opt.textContent=name;opt.selected=idx+1===jView.jm;monthSelect.appendChild(opt);});
        const yearSelect=document.createElement('select');yearSelect.className='sac-cal-select sac-cal-select-year';yearSelect.setAttribute('aria-label','انتخاب سال شمسی');
        const fromYear=Math.min(1300,jView.jy-30),toYear=Math.max(1500,jView.jy+30);
        for(let yr=fromYear;yr<=toYear;yr++){const opt=document.createElement('option');opt.value=String(yr);opt.textContent=String(yr);opt.selected=yr===jView.jy;yearSelect.appendChild(opt);}
        const navigate=delta=>{const index=(jView.jy*12+jView.jm-1)+delta;jView={jy:Math.floor(index/12),jm:(index%12+12)%12+1};render();popup.hidden=false;};
        previous.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();navigate(-1);});
        next.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();navigate(1);});
        monthSelect.addEventListener('change',event=>{event.stopPropagation();jView.jm=Number(monthSelect.value);render();popup.hidden=false;});
        yearSelect.addEventListener('change',event=>{event.stopPropagation();jView.jy=Number(yearSelect.value);render();popup.hidden=false;});
        heading.append(monthSelect,yearSelect);header.append(previous,heading,next);popup.appendChild(header);
        const grid=document.createElement('div');grid.className='sac-cal-grid';
        weekdays.forEach(w=>{const el=document.createElement('span');el.className='sac-cal-weekday';el.textContent=w;grid.appendChild(el);});
        const first=toG(jView.jy,jView.jm,1);
        const start=(new Date(Date.UTC(first.gy,first.gm-1,first.gd)).getUTCDay()+1)%7;
        for(let i=0;i<start;i++){grid.appendChild(document.createElement('span'));}
        for(let day=1;day<=monthLength(jView.jy,jView.jm);day++){
          const btn=document.createElement('button');btn.type='button';btn.className='sac-cal-day';btn.textContent=String(day);
          const date=gregorianFromJalali(jView.jy,jView.jm,day);
          if(date===chosen)btn.classList.add('is-picked');
          btn.addEventListener('click',()=>{
            input.dataset.gdate=date;input.value=jalaliDisplay(date);card._datesDirty[field]=true;
            closeCalendar();sync();
          }); grid.appendChild(btn);
        }
        popup.appendChild(grid);
        const today=document.createElement('button');today.type='button';today.className='btn btn-sm btn-light-primary sac-cal-today';today.textContent='امروز';
        today.addEventListener('click',()=>{
          const now=new Date();const utcNow=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
          input.dataset.gdate=utcNow;input.value=jalaliDisplay(utcNow);card._datesDirty[field]=true;closeCalendar();sync();
        });popup.appendChild(today);
      }
      input.addEventListener('click',event=>{
        if(!editable)return;
        event.stopPropagation();
        if(openCal===popup){closeCalendar();return;}
        closeCalendar();
        const selected=input.dataset.gdate;
        const today=new Date();
        const current=selected || `${today.getUTCFullYear()}-${pad(today.getUTCMonth()+1)}-${pad(today.getUTCDate())}`;
        const [gy,gm,gd]=current.split('-').map(Number);jView=toJ(gy,gm,gd);
        render();popup.hidden=false;openCal=popup;positionCalendar();
      });
      clear.addEventListener('click',()=>{if(!editable)return;input.value='';input.dataset.gdate='';card._datesDirty[field]=true;closeCalendar();sync();});
      if(!editable)clear.hidden=true;
    }

    let showSubmitError=false;
    let lastTotal=NaN;
    let syncRequested=false;
    function scheduleSync(){if(syncRequested)return;syncRequested=true;requestAnimationFrame(()=>{syncRequested=false;sync(false);});}
    function setPrepaymentOptions(card){
      const mode=card.querySelector('[data-sac="mode"]').value;
      const percent=card.querySelector('[data-sac="percent"]');
      const payment=card.querySelector('[data-sac="payment_amount"]');
      percent.readOnly=!editable||mode!=='percent';
      payment.readOnly=!editable||mode!=='amount';
      percent.classList.toggle('sac-derived',mode!=='percent');
      payment.classList.toggle('sac-derived',mode!=='amount');
      for(const [input,locked] of [[percent,mode!=='percent'],[payment,mode!=='amount']]){
        input.setAttribute('aria-readonly',String(!editable||locked));
        input.tabIndex=(!editable||locked)?-1:0;
        input.title=locked?'مقدار محاسبه‌شده و غیرقابل ویرایش':'مقدار قابل ویرایش';
        const field=input.closest('.sac-field');
        field.classList.toggle('sac-derived-field',locked);
        field.classList.toggle('sac-editable-field',editable&&!locked);
      }
    }
    function addRow(source){
      const item=source&&typeof source==='object'?source:{};
      const card=document.createElement('div');
      card.className='sac-row sac-single-line'+(editable?'':' sac-readonly');
      card._source=Object.assign({},item);card._datesDirty={};
      const type=['cash','check','advance'].includes(item.type)?item.type:'cash';
      const mode=['amount','percent'].includes(item.input_mode)?item.input_mode:'percent';
      const storedPercentage=item.percentage!=null ? decimal(item.percentage) : decimal(item.amount)*100;
      const storedAmount=item.payment_amount!=null ? decimal(item.payment_amount):NaN;
      const inputVal=item.input_value!=null?decimal(item.input_value):NaN;
      const fraction=Number.isFinite(storedPercentage)?storedPercentage:0;
      const collectionDate=ymdFromStored(item['Check Collection Date']);
      const receiptDate=ymdFromStored(item['Receipt Date']);
      card.innerHTML=`
        <div class="sac-row-header"><span class="sac-number">شرط پرداخت</span>
          <button type="button" class="btn btn-sm btn-light-danger" data-action="remove" title="حذف شرط" aria-label="حذف شرط">×</button></div>
        <div class="sac-grid sac-v6-grid">
          <div class="sac-field"><label>نوع پرداخت</label><select class="form-select form-select-sm" data-sac="type">${selectOptions([['cash','نقدی'],['check','چک'],['advance','پیش‌پرداخت']],type)}</select></div>
          <div class="sac-field"><label>مبنای ورود</label><select class="form-select form-select-sm" data-sac="mode">${selectOptions([['percent','درصد'],['amount','مبلغ']],mode)}</select></div>
          <div class="sac-field"><label>درصد پرداخت (%)</label><input class="form-control form-control-sm" data-sac="percent" type="text" inputmode="decimal" value="${escaping(mode==='percent'&&Number.isFinite(inputVal)?fixed(inputVal):fixed(fraction))}" placeholder="درصد"></div>
          <div class="sac-field"><label>مبلغ پرداخت</label><input class="form-control form-control-sm" data-sac="payment_amount" type="text" inputmode="decimal" value="${escaping(formatPaymentAmount(mode==='amount'&&Number.isFinite(inputVal)?fixed(inputVal,2):Number.isFinite(storedAmount)?fixed(storedAmount,2):''))}" placeholder="مبلغ"></div>
          <div class="sac-field sac-only-check"><label>تاریخ دریافت چک</label>
            <div class="sac-date-wrap"><input class="form-control sac-date-trigger" data-sac="collection" type="text" readonly placeholder="تاریخ شمسی" value="${escaping(jalaliDisplay(collectionDate))}"><button class="sac-date-clear" type="button" title="پاک کردن">×</button><div class="sac-cal" hidden></div></div>
          </div>
          <div class="sac-field"><label data-sac="receipt-label">${type==='check'?'تاریخ وصول چک':'تاریخ دریافت پول'}</label>
            <div class="sac-date-wrap"><input class="form-control sac-date-trigger" data-sac="receipt" type="text" readonly placeholder="تاریخ شمسی" value="${escaping(jalaliDisplay(receiptDate))}"><button class="sac-date-clear" type="button" title="پاک کردن">×</button><div class="sac-cal" hidden></div></div>
          </div>
        </div>`;
      for(const name of ['collection','receipt']){
        const input=card.querySelector(`[data-sac="${name}"]`);
        input.dataset.gdate=name==='collection'?collectionDate:receiptDate;
        attachCalendar(card,input,name);
        if(!editable)input.disabled=true;
      }
      card.querySelector('[data-action="remove"]').addEventListener('click',()=>{
        closeCalendar();
        card.querySelectorAll('.sac-date-trigger').forEach(input=>{
          // Calendar nodes are portaled into document.body; remove orphan popups.
          const popup=input._sacPopup;
          if(popup)popup.remove();
        });
        card.remove();renumber();scheduleSync();
      });
      card.querySelectorAll('[data-sac="type"],[data-sac="mode"],[data-sac="percent"],[data-sac="payment_amount"]').forEach(input=>{
        if(!editable)input.disabled=true;
        input.addEventListener('input',()=>{if(input.dataset.sac==='type')toggleCheck(card);if(input.dataset.sac==='mode')setPrepaymentOptions(card);scheduleSync();});
        input.addEventListener('change',()=>{if(input.dataset.sac==='type')toggleCheck(card);if(input.dataset.sac==='mode')setPrepaymentOptions(card);scheduleSync();});
      });
      rows.appendChild(card);toggleCheck(card);setPrepaymentOptions(card);renumber();
    }
    function toggleCheck(card){
      const check=card.querySelector('[data-sac="type"]').value==='check';
      card.querySelector('.sac-only-check').hidden=!check;
      card.classList.toggle('sac-is-check',check);
      card.querySelector('[data-sac="receipt-label"]').textContent=check?'تاریخ وصول چک':'تاریخ دریافت پول';
      if(!check&&editable){
        const c=card.querySelector('[data-sac="collection"]');
        if(c.dataset.gdate){c.dataset.gdate='';c.value='';card._datesDirty.collection=true;}
      }
    }
    function renumber(){
      const current=Array.from(rows.querySelectorAll('.sac-row'));
      current.forEach((card,i)=>card.querySelector('.sac-number').textContent=`شرط پرداخت ${i+2}`);
      if(addBottom)addBottom.hidden=current.length<2;
    }
    function makeItems(strict){
      const total=invoiceTotal();
      // Price may not have been calculated yet on a draft: use zero, not a blocking error.
      // A negative final price is also treated as zero for the payment preview.
      // invoiceTotal() always yields a finite nonnegative number.
      const data=[];let sum=0;
      rows.querySelectorAll('.sac-row').forEach((card,i)=>{
        const get=name=>card.querySelector(`[data-sac="${name}"]`);
        const mode=get('mode').value;
        // sac-v9-empty-payment-zero: empty editor value is zero, while malformed/negative values remain invalid.
        const chosenInput=get(mode==='percent'?'percent':'payment_amount');
        const rawChosen=normalizeDigits(chosenInput.value).replace(/[٬,،\s\u00a0]/g,'').trim();
        const chosen=rawChosen===''?0:decimal(chosenInput.value);
        if(!Number.isFinite(chosen)||chosen<0){
          throw new Error(`شرط ${i+2}: مقدار ${mode==='percent'?'درصد':'مبلغ'} نامعتبر است.`);
        }
        // Do not overwrite the input during typing. Normalize it on submit/blur.
        if(strict && rawChosen==='')chosenInput.value='0';
        let percent,payment;
        if(mode==='percent'){
          percent=chosen;payment=total*percent/100;
          get('payment_amount').value=formatPaymentAmount(moneyValue(payment));
        }else{
          payment=chosen;percent=total>0 ? payment/total*100 : 0;
          get('percent').value=fixed(percent);
        }
        const item=Object.assign({},card._source);
        delete item.item_scope;
        item.is_system=false;
        item.type=get('type').value;
        item.input_mode=mode;
        item.input_value=fixed(chosen,mode==='amount'?2:8);
        item.percentage=fixed(percent);
        item.payment_amount=moneyValue(payment);
        item.amount=fixed(percent/100);
        for(const key of ['collection','receipt']){
          const prop=key==='collection'?'Check Collection Date':'Receipt Date';
          if(key==='collection'&&item.type!=='check'){item[prop]=null;continue;}
          const gdate=get(key).dataset.gdate;
          item[prop]=card._datesDirty[key] ? toStoredDate(gdate,item[prop]):(item[prop]||null);
          if(strict&&chosen>0&&!item[prop])throw new Error(`شرط ${i+2}: ${key==='collection'?'تاریخ دریافت چک':(item.type==='check'?'تاریخ وصول چک':'تاریخ دریافت پول')} را انتخاب کنید.`);
        }
        if(item.type==='check'&&item['Check Collection Date']&&item['Receipt Date']&&ymdFromStored(item['Receipt Date'])<ymdFromStored(item['Check Collection Date'])){
          throw new Error(`شرط ${i+2}: تاریخ وصول چک قبل از تاریخ دریافت آن است.`);
        }
        if(item.type!=='check')delete item.date_rule;
        if(card._datesDirty.receipt)delete item.date_rule;
        sum+=Number(moneyValue(payment));data.push(item);
      });
      const remaining=Math.max(0,total-sum);
      const remainingPercent=total>0 ? (remaining/total)*100 : 0;
      const system={
        type:'cash',is_system:true,input_mode:'amount',input_value:moneyValue(remaining),
        payment_amount:moneyValue(remaining),percentage:fixed(remainingPercent),amount:fixed(remainingPercent/100),
        base_total:moneyValue(total),'Check Collection Date':null,'Receipt Date':null
      };
      return {items:[system,...data],total,remaining,sum};
    }
    function renderSummary(result){
      const {items,total,remaining,sum}=result;
      const first=items[0];
      totalText.textContent=displayMoney(total);
      cashAmount.textContent=displayMoney(remaining);
      cashPercent.textContent=fixed(Number(first.percentage),2)+'٪';
      const breakdown={cash:0,check:0,advance:0};
      items.forEach(it=>{if(Object.prototype.hasOwnProperty.call(breakdown,it.type))breakdown[it.type]+=Number(it.percentage||0);});
      const manualPercent=total>0 ? sum/total*100 : 0;
      const over=sum>total+0.000001;
      summary.innerHTML=`<span class="sac-summary-chip${over?' sac-over':''}">پرداخت‌های دستی: ${fixed(manualPercent,2)}٪</span><span class="sac-summary-chip">مانده نقدی: ${displayMoney(remaining)}</span>`+
        (over?'<span class="sac-overview-alert" role="alert">هشدار: مبلغ پرداخت‌ها بیش از مبلغ نهایی سند است؛ ذخیره مجاز است.</span>':'');
      overview.innerHTML='<span class="sac-overview-label">برنامه پرداخت:</span>'+[['cash','نقدی'],['check','چک'],['advance','پیش‌پرداخت']]
        .filter(([type])=>breakdown[type]>0).map(([type,label])=>`<span class="sac-overview-chip" data-kind="${type}"><span class="sac-overview-dot"></span>${label} ${fixed(breakdown[type],2)}٪</span>`).join('')+
        `<span class="sac-overview-chip" data-kind="total">جمع ${fixed(Object.values(breakdown).reduce((a,b)=>a+b,0),2)}٪</span>`+
        (over?'<span class="sac-overview-alert">بیشتر از ۱۰۰٪</span>':'');
    }
    function sync(strict=false){
      if(conditions===null)return false;
      if(root.hidden)return true;
      try {
        const computed=makeItems(strict);
        renderSummary(computed);
        if(editable)hiddenInputs().forEach(input=>{input.value=JSON.stringify(computed.items);});
        if(strict){showSubmitError=false;showError('');}
        else if(!showSubmitError)showError('');
        lastTotal=computed.total;
        return true;
      }catch(e){
        if(strict){showSubmitError=true;showError(e.message||'در ذخیره‌سازی شرایط پرداخت خطایی رخ داده است.');}
        else {summary.innerHTML='<span class="sac-overview-alert">اطلاعات بعضی ردیف‌ها هنوز کامل نیست</span>';overview.innerHTML='<span class="sac-overview-empty">در انتظار تکمیل شرایط پرداخت</span>';}
        return false;
      }
    }
    function replaceFromQuotation(items){
      if(!editable||!Array.isArray(items))return;
      const currentManual=Array.from(rows.querySelectorAll('.sac-row'));
      const newManual=items.filter(it=>!(it&&it.is_system===true));
      if(currentManual.length && JSON.stringify(initialManual)===JSON.stringify(newManual))return;
      if(currentManual.length && !window.confirm('شرایط پرداخت فعلی با شرایط پیش‌فاکتور جایگزین شوند؟'))return;
      closeCalendar();
      rows.querySelectorAll('.sac-date-trigger').forEach(input=>input._sacPopup?.remove());
      rows.replaceChildren();conditions=items;
      initialManual=items.filter(it=>!(it&&it.is_system===true));
      initialManual.forEach(addRow);scheduleSync();
    }
    if(conditions===null){showError('JSON فعلی قابل خواندن نیست و برای جلوگیری از حذف ناخواسته، ذخیره متوقف شده است.');}
    else {initialManual.forEach(addRow);renumber();}
    toggleVisibility();
    if(saleType){saleType.addEventListener('change',toggleVisibility);if(window.jQuery)window.jQuery(saleType).on('change select2:select select2:clear',toggleVisibility);}
    function addCondition(){
      addRow({type:'cash',input_mode:'percent',input_value:'',amount:''});
      if(details)details.open=true;
      scheduleSync();
      const latest=rows.querySelector('.sac-row:last-child');
      latest?.querySelector('[data-sac="percent"]')?.focus();
    }
    if(addBtn)addBtn.addEventListener('click',addCondition);
    if(addBottom)addBottom.addEventListener('click',addCondition);
    window.addEventListener('sac:prefactor-loaded',e=>{if(documentType==='factor'&&e.detail&&Array.isArray(e.detail.conditions))replaceFromQuotation(e.detail.conditions);});
    // Existing Factor pages select quotations by Select2. Load just the payment
    // defaults after selection; no save occurs and existing factors are untouched.
    if(documentType==='factor'&&window.jQuery){
      window.jQuery(document).on('select2:select','#id_select_quotation_for_factor',function(event){
        const pk=event.params&&event.params.data&&event.params.data.id;
        if(!pk || !/^\d+$/.test(String(pk)))return;
        fetch(`/factor/prefactor/${pk}/json/`,{headers:{'X-Requested-With':'XMLHttpRequest'}})
          .then(response=>{if(!response.ok)throw new Error('prefactor HTTP '+response.status);return response.json();})
          .then(payload=>{if(Array.isArray(payload.sale_type_multi_condition))replaceFromQuotation(payload.sale_type_multi_condition);})
          .catch(err=>showError('خطا در دریافت شرایط پرداخت پیش‌فاکتور: '+err.message));
      });
    }
    // Handles create links (?q_id, ?pk or ?from) that pre-select a quotation
    // without emitting a Select2 event, and keeps saved factors untouched.
    if(documentType==='factor' && !documentId && initialManual.length===0){
      const params=new URLSearchParams(window.location.search);
      const initialPk=params.get('q_id')||params.get('from')||params.get('pk');
      if(initialPk && /^\d+$/.test(initialPk)){
        fetch(`/factor/prefactor/${initialPk}/json/`,{headers:{'X-Requested-With':'XMLHttpRequest'}})
          .then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();})
          .then(payload=>{
            if(Array.isArray(payload.sale_type_multi_condition) && rows.children.length===0){
              replaceFromQuotation(payload.sale_type_multi_condition);
            }
          })
          .catch(err=>showError('دریافت شرایط پرداخت پیش‌فاکتور انجام نشد: '+err.message));
      }
    }
    // sac-v9: show 0 after the user leaves an empty editable payment input.
    root.addEventListener('blur',event=>{
      const input=event.target;
      if(!input || !input.matches('[data-sac="percent"],[data-sac="payment_amount"]') || input.readOnly || input.disabled)return;
      const plain=normalizeDigits(input.value).replace(/[٬,،\s\u00a0]/g,'').trim();
      if(plain===''){input.value='0';scheduleSync();}
    },true);
    root.addEventListener('input',()=>{showSubmitError=false;},true);
    root.addEventListener('click',event=>{if(event.target.closest('.sac-cal')||event.target.closest('.sac-date-clear'))showSubmitError=false;},true);
    if(form&&editable)form.addEventListener('submit',event=>{
      if(root.hidden)return;
      if(!sync(true)){
        event.preventDefault();event.stopImmediatePropagation();
        if(details)details.open=true;
        error.scrollIntoView({behavior:'smooth',block:'center'});
      }
    },true);
    // Totals are refreshed by the existing quotation/factor price-calculation scripts.
    // Observe only the provided total element, not the whole form (avoids loops).
    const totalElement=document.querySelector(totalSelector);
    if(totalElement){new MutationObserver(scheduleSync).observe(totalElement,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['value']});totalElement.addEventListener('input',scheduleSync);}
    form&&form.addEventListener('input',event=>{if(event.target&&event.target.closest('#sac-root'))return;if(/price|quantity|discount|tax|duty|addition/i.test(event.target?.name||''))scheduleSync();},true);
    scheduleSync();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
  if(typeof window!=='undefined')window.__sacJalaliTest={toJ,toG,jalaliDisplay,gregorianFromJalali};
})();
