/* Run: node tools/test_trade_payment_calendar.js (no dependencies). */
function runCalendarTests(source) {
    let count = 0;
    const assert = (condition, label) => {
        if (!condition) throw new Error(label);
        count++;
    };
    const api = new Function(source + ';return TradePaymentCalendar;')();
    assert(api.format('2026-11-28') === '1405/09/07', 'known November date');
    assert(api.iso(1405,9,7) === '2026-11-28', 'known Persian date');
    assert(api.iso(1403,12,30) === '2025-03-20', 'leap day');
    assert(api.iso(1404,12,30) === '', 'non-leap day rejected');
    assert(api.format('2026-02-30') === '', 'invalid Gregorian date rejected');
    assert(api.format('2026-03-21') === '1405/01/01', 'Nowruz');
    assert(api.format('1821-03-21') === '1200/01/01', 'lower supported date');
    assert(api.format('2222-03-20') === '1600/12/29', 'upper supported date');
    assert(api.format('2222-03-21') === '', 'outside supported date');
    let roundTrips = true;
    for (let y=1200; y<=1600; y++) {
        for (let m=1; m<=12; m++) {
            for (let d=1; d<=31; d++) {
                const iso = api.iso(y,m,d);
                if (iso && api.format(iso) !== [y,String(m).padStart(2,'0'),String(d).padStart(2,'0')].join('/')) roundTrips=false;
            }
        }
    }
    assert(roundTrips, 'every valid day in supported Jalali years round-trips');

    // Minimal DOM fixture: exercise actual setup/switch events without browser dependencies.
    function element() {
        const listeners = {}, classes = new Set(), attributes = {};
        return {
            value:'', textContent:'', dataset:{}, style:{}, hidden:false,
            classList:{toggle(key,on){if(on)classes.add(key);else classes.delete(key);}, contains:key=>classes.has(key)},
            setAttribute(key,value){attributes[key]=value;},
            addEventListener(key,fn){listeners[key]=fn;},
            fire(key){listeners[key]?.({target:this});},
            focus(){},
        };
    }
    const fields = {};
    ['Start','End'].forEach(key=>{
        ['','Jalali','Equivalent'].forEach(suffix=>{fields['tradePayment'+key+suffix]=element();});
    });
    const g = element(), j = element();
    g.dataset.paymentCalendar='gregorian'; j.dataset.paymentCalendar='jalali';
    const document = {
        getElementById:id=>fields[id],
        querySelectorAll:()=>[g,j],
        createElement:element,
        body:{appendChild(){}},
        addEventListener(){},
    };
    const window={addEventListener(){}};
    let saved='gregorian';
    const localStorage={getItem:()=>saved,setItem:(key,value)=>{saved=value;}};
    const ui = new Function('document','window','localStorage',source+';return TradePaymentCalendar;')(document,window,localStorage);
    fields.tradePaymentStart.value='2026-11-28';
    fields.tradePaymentEnd.value='2026-12-05';
    let changes=0;
    const controls=ui.setup(()=>changes++);
    j.fire('click');
    assert(controls.mode()==='jalali' && saved==='jalali','Jalali selection persists');
    assert(fields.tradePaymentStart.value==='2026-11-28' && fields.tradePaymentEnd.value==='2026-12-05','ISO values unchanged when switching');
    assert(fields.tradePaymentStartJalali.textContent==='1405/09/07','Jalali display synchronized');
    assert(fields.tradePaymentStartEquivalent.textContent==='2026/11/28 میلادی','Gregorian equivalent visible');
    assert(fields.tradePaymentStart.classList.contains('d-none') && !fields.tradePaymentStartJalali.classList.contains('d-none'),'only chosen picker visible');
    g.fire('click');
    assert(controls.mode()==='gregorian' && saved==='gregorian','Gregorian selection persists');
    assert(fields.tradePaymentStart.value==='2026-11-28' && fields.tradePaymentEnd.value==='2026-12-05','ISO values unchanged switching back');
    assert(fields.tradePaymentStartEquivalent.textContent==='1405/09/07 شمسی','Jalali equivalent visible');
    assert(changes===2,'switch triggers change notification');
    return count;
}
if (typeof module !== 'undefined' && require.main === module) {
    const fs = require('node:fs');
    const path = require('node:path');
    const source = fs.readFileSync(path.join(__dirname,'../assets/js/local/trade-payment-calendar.js'),'utf8');
    console.log(runCalendarTests(source) + ' calendar checks passed');
}
