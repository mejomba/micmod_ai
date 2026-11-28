/* Isolated payment calendar; conversion from bundled jalaali-js v1.1.0 (MIT),
 * as used in quick_packing_date_calendar.js. Canonical dates remain ISO Gregorian. */
const TradePaymentCalendar = (() => {
function toJalaali(a,i,d){return"[object Date]"===Object.prototype.toString.call(a)&&(d=a.getDate(),i=a.getMonth()+1,a=a.getFullYear()),d2j(g2d(a,i,d))}function toGregorian(a,i,d){return d2g(j2d(a,i,d))}function isValidJalaaliDate(a,i,d){return a>=-61&&a<=3177&&i>=1&&i<=12&&d>=1&&d<=jalaaliMonthLength(a,i)}function isLeapJalaaliYear(a){return 0===jalCal(a).leap}function jalaaliMonthLength(a,i){return i<=6?31:i<=11||isLeapJalaaliYear(a)?30:29}function jalCal(a){var i,d,t,l,r,n,e=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178],o=e.length,v=a+621,g=-14,u=e[0];if(a<u||a>=e[o-1])throw new Error("Invalid Jalaali year "+a);for(n=1;n<o&&(d=(i=e[n])-u,!(a<i));n+=1)g=g+8*div(d,33)+div(mod(d,33),4),u=i;return g=g+8*div(r=a-u,33)+div(mod(r,33)+3,4),4===mod(d,33)&&d-r==4&&(g+=1),l=20+g-(div(v,4)-div(3*(div(v,100)+1),4)-150),d-r<6&&(r=r-d+33*div(d+4,33)),-1===(t=mod(mod(r+1,33)-1,4))&&(t=4),{leap:t,gy:v,march:l}}function j2d(a,i,d){var t=jalCal(a);return g2d(t.gy,3,t.march)+31*(i-1)-div(i,7)*(i-7)+d-1}function d2j(a){var i,d=d2g(a).gy,t=d-621,l=jalCal(t);if((i=a-g2d(d,3,l.march))>=0){if(i<=185)return{jy:t,jm:1+div(i,31),jd:mod(i,31)+1};i-=186}else t-=1,i+=179,1===l.leap&&(i+=1);return{jy:t,jm:7+div(i,30),jd:mod(i,30)+1}}function g2d(a,i,d){var t=div(1461*(a+div(i-8,6)+100100),4)+div(153*mod(i+9,12)+2,5)+d-34840408;return t=t-div(3*div(a+100100+div(i-8,6),100),4)+752}function d2g(a){var i,d,t,l;return i=(i=4*a+139361631)+4*div(3*div(4*a+183187720,146097),4)-3908,d=5*div(mod(i,1461),4)+308,t=div(mod(d,153),5)+1,l=mod(div(d,153),12)+1,{gy:div(i,1461)-100100+div(8-l,6),gm:l,gd:t}}function div(a,i){return~~(a/i)}function mod(a,i){return a-~~(a/i)*i}
    const months = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
    const pad = n => String(n).padStart(2, '0');
    function persian(iso) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
        if (!match) return null;
        const [, y, m, d] = match.map(Number);
        if (y < 1821 || y > 2221) return null;
        const checked = new Date(Date.UTC(y,m-1,d));
        if (checked.getUTCFullYear() !== y || checked.getUTCMonth()+1 !== m || checked.getUTCDate() !== d) return null;
        const j = toJalaali(y,m,d);
        return j.jy >= 1200 && j.jy <= 1600 ? j : null;
    }
    function iso(y,m,d) {
        if (y < 1200 || y > 1600 || !isValidJalaaliDate(y,m,d)) return '';
        const g = toGregorian(y,m,d);
        return [g.gy,pad(g.gm),pad(g.gd)].join('-');
    }
    function format(isoDate) {
        const j = persian(isoDate);
        return j ? [j.jy,pad(j.jm),pad(j.jd)].join('/') : '';
    }
    function setup(onChange) {
        const fields = ['Start','End'].map(key => ({
            input: document.getElementById('tradePayment'+key),
            display: document.getElementById('tradePayment'+key+'Jalali'),
            equivalent: document.getElementById('tradePayment'+key+'Equivalent')
        }));
        const buttons = Array.from(document.querySelectorAll('[data-payment-calendar]'));
        const popup = document.createElement('div');
        popup.className = 'tp-calendar-popup';
        popup.id = 'tradePaymentCalendarPopup';
        popup.hidden = true;
        popup.setAttribute('role','dialog');
        popup.setAttribute('aria-label','تقویم شمسی');
        document.body.appendChild(popup);
        let active = null, shown = null, mode = 'gregorian';
        try { if (localStorage.getItem('tradePaymentCalendar') === 'jalali') mode = 'jalali'; } catch (_) {}
        function today() {
            const now = new Date();
            return toJalaali(now.getFullYear(),now.getMonth()+1,now.getDate());
        }
        function sync() {
            fields.forEach(({input,display,equivalent}) => {
                const j = format(input.value);
                display.textContent = j || 'انتخاب تاریخ شمسی ▦';
                equivalent.textContent = input.value ? (mode === 'jalali' ? input.value.replace(/-/g,'/') + ' میلادی' : (j ? j + ' شمسی' : '')) : '';
                input.classList.toggle('d-none',mode === 'jalali');
                display.classList.toggle('d-none',mode !== 'jalali');
            });
            buttons.forEach(button => {
                const selected = button.dataset.paymentCalendar === mode;
                button.classList.toggle('active',selected);
                button.setAttribute('aria-pressed',String(selected));
            });
        }
        function close(restoreFocus=false) {
            if (active) {
                active.display.setAttribute('aria-expanded','false');
                if (restoreFocus) active.display.focus();
            }
            active = null; popup.hidden = true;
        }
        function position() {
            if (!active) return;
            const rect = active.display.getBoundingClientRect();
            const width = popup.offsetWidth, height = popup.offsetHeight;
            popup.style.left = Math.max(8,Math.min(window.innerWidth-width-8,rect.right-width))+'px';
            popup.style.top = Math.max(8,Math.min(window.innerHeight-height-8,
                rect.bottom+height+5 > window.innerHeight && rect.top > height ? rect.top-height-5 : rect.bottom+5))+'px';
        }
        function add(container,label,aria,fn,cls='btn btn-sm btn-light') {
            const button = document.createElement('button');
            button.type='button'; button.className=cls; button.textContent=label;
            button.setAttribute('aria-label',aria);
            button.addEventListener('click',fn);
            container.appendChild(button);
            return button;
        }
        function choose(y,m,d) {
            if (!active) return;
            const value = iso(y,m,d);
            if (!value) return;
            active.input.value=value;
            active.input.dispatchEvent(new Event('change',{bubbles:true}));
            close(true);
        }
        function shift(delta) {
            const index = shown.jy*12+shown.jm-1+delta;
            const y = Math.floor(index/12), m = index%12+1;
            if (y < 1200 || y > 1600) return;
            shown={jy:y,jm:m}; render();
        }
        function render() {
            popup.replaceChildren();
            const header = document.createElement('div'); header.className='tp-calendar-head';
            add(header,'»','سال قبل',()=>shift(-12));
            add(header,'›','ماه قبل',()=>shift(-1));
            const label=document.createElement('strong'); label.textContent=months[shown.jm-1]+' '+shown.jy;
            header.appendChild(label);
            add(header,'‹','ماه بعد',()=>shift(1));
            add(header,'«','سال بعد',()=>shift(12));
            popup.appendChild(header);
            const grid=document.createElement('div'); grid.className='tp-calendar-grid';
            ['ش','ی','د','س','چ','پ','ج'].forEach(day=>{const e=document.createElement('small');e.className='text-muted';e.textContent=day;grid.appendChild(e);});
            const first=toGregorian(shown.jy,shown.jm,1);
            const offset=(new Date(Date.UTC(first.gy,first.gm-1,first.gd)).getUTCDay()+1)%7;
            for(let i=0;i<offset;i++) grid.appendChild(document.createElement('span'));
            const selected=active.input.value, now=today();
            for(let d=1;d<=jalaaliMonthLength(shown.jy,shown.jm);d++){
                const value=iso(shown.jy,shown.jm,d);
                const btn=add(grid,String(d),format(value),()=>choose(shown.jy,shown.jm,d),'tp-day');
                if(value===selected){btn.classList.add('is-selected');btn.setAttribute('aria-pressed','true');}
                if(now.jy===shown.jy && now.jm===shown.jm && now.jd===d)btn.classList.add('is-today');
            }
            popup.appendChild(grid);
            const footer=document.createElement('div');footer.className='tp-calendar-foot';
            add(footer,'پاک کردن','پاک کردن تاریخ',()=>{active.input.value='';active.input.dispatchEvent(new Event('change',{bubbles:true}));close(true);});
            add(footer,'امروز','انتخاب امروز',()=>{const j=today();choose(j.jy,j.jm,j.jd);},'btn btn-sm btn-light-primary');
            popup.appendChild(footer);
            popup.hidden=false;position();
        }
        fields.forEach(field=>{
            field.display.setAttribute('aria-controls',popup.id);
            field.display.addEventListener('click',()=>{
                if(active===field){close(true);return;}
                close();
                active=field;shown=persian(field.input.value)||today();
                field.display.setAttribute('aria-expanded','true');render();
                (popup.querySelector('.is-selected')||popup.querySelector('.is-today')||popup.querySelector('.tp-day'))?.focus();
            });
            field.input.addEventListener('change',()=>{sync();onChange();});
        });
        buttons.forEach(button=>button.addEventListener('click',()=>{
            close(); mode=button.dataset.paymentCalendar;
            try{localStorage.setItem('tradePaymentCalendar',mode);}catch(_){}
            sync();onChange();
        }));
        document.addEventListener('pointerdown',event=>{if(active&&!popup.contains(event.target)&&!fields.some(f=>f.display.contains(event.target)))close();});
        document.addEventListener('keydown',event=>{if(active&&event.key==='Escape'){event.preventDefault();close(true);}});
        window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
        sync();
        return {sync,close, mode:()=>mode};
    }
    return {setup,format,iso,persian};
})();
