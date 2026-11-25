/* Recursive condition builder. Never evaluates expressions; server validates the AST. */
(function () {
  "use strict";
  const host = document.getElementById("condition-builder");
  if (!host) return;
  const form = document.getElementById("scheduling-editor");
  const hidden = document.getElementById("id_condition_json");
  const tree = document.getElementById("condition-tree");
  const error = document.getElementById("condition-error");
  const fields = JSON.parse(document.getElementById("scheduling-field-metadata").textContent);
  const fa = host.dataset.fa === "1";
  const t = (a,b) => fa ? a : b;
  const node = (tag, cls, text) => { const el = document.createElement(tag); if(cls) el.className=cls; if(text) el.textContent=text; return el; };
  const btn = (text,fn) => {const b=node("button","btn btn-sm btn-light",text);b.type="button";b.addEventListener("click",fn);return b;};
  function select(items, value) {const s=node("select","form-select form-select-sm w-auto");items.forEach(([key,label])=>{const opt=node("option","",label);opt.value=key;s.append(opt);});if(value!==undefined)s.value=value;return s;}
  function build(value, depth) {
    if(depth>12) throw new Error(t("عمق شرط بیش از حد است","Condition depth exceeded"));
    const wrap=node("div","border rounded p-2 my-2");
    let type = value.and ? "and" : value.or ? "or" : value.not ? "not" : value.field ? "leaf" : "always";
    const kind=select([["always",t("همیشه","Always")],["leaf",t("شرط","Condition")],["and",t("همه شروط (AND)","All (AND)")],["or",t("یکی از شروط (OR)","Any (OR)")],["not",t("نقیض (NOT)","Not")]],type);
    const body=node("div","mt-2");wrap.append(kind,body);
    let read=()=>({});
    function render(v) {
      body.replaceChildren();
      type=kind.value;
      if(type==="always"){read=()=>({});return;}
      if(type==="leaf"){
        const line=node("div","d-flex flex-wrap align-items-center gap-2");
        const field=select(fields.map(f=>[f.key,f.label]),v.field||fields[0]?.key);
        const opSlot=node("div","d-flex gap-2 flex-wrap");
        line.append(field,opSlot);body.append(line);
        function operators(initial) {
          opSlot.replaceChildren();
          const f=fields.find(x=>x.key===field.value);
          if(!f)throw new Error("No registered fields");
          const opts=[["eq",t("برابر","Equals")],["ne",t("نابرابر","Not equal")],
            ["in",t("در مجموعه","In")],["not_in",t("خارج مجموعه","Not in")],
            ["is_null",t("نامشخص","Is null")],["is_not_null",t("مشخص","Is not null")]];
          if(["number","date"].includes(f.kind)) opts.push(["gt",">"],["gte",">="],["lt","<"],["lte","<="]);
          const op=select(opts,initial.operator||"eq");opSlot.append(op);
          const valSlot=node("div","d-flex gap-2");opSlot.append(valSlot);
          function input(existing) {
            valSlot.replaceChildren();
            const member=["in","not_in"].includes(op.value);
            if(["is_null","is_not_null"].includes(op.value)){read=()=>({field:f.key,operator:op.value});return;}
            let control;
            const choices=f.choices.length?f.choices:f.kind==="boolean"?[true,false]:[];
            if(choices.length){
              control=select(choices.map(x=>[String(x),String(x)]));
              if(member){control.multiple=true; Array.from(control.options).forEach(o=>{o.selected=(Array.isArray(existing)?existing:[]).map(String).includes(o.value);});}
              else if(existing!==undefined)control.value=String(existing);
            }else{
              control=node("input","form-control form-control-sm");
              control.type=member?"text":f.kind==="number"?"number":f.kind==="date"?"date":"text";
              if(control.type==="number")control.step="any";
              if(member)control.placeholder=t("مقادیر با کاما","Comma-separated values");
              control.value=Array.isArray(existing)?existing.join(", "):existing??"";
            }
            valSlot.append(control);
            function convert(raw){
              if(raw==="")throw new Error(t("مقدار شرط را وارد کنید","Enter a condition value"));
              if(f.kind==="number"){const x=Number(raw);if(!Number.isFinite(x))throw new Error("Invalid number");return x;}
              if(f.kind==="boolean"){if(!["true","false"].includes(raw))throw new Error("Invalid boolean");return raw==="true";}
              return raw;
            }
            read=()=>({field:f.key,operator:op.value,value:member?(control.multiple?Array.from(control.selectedOptions,o=>convert(o.value)):control.value.split(",").map(x=>convert(x.trim()))):convert(control.value)});
          }
          op.addEventListener("change",()=>input(undefined));input(initial.value);
        }
        field.addEventListener("change",()=>operators({}));operators(v);return;
      }
      const children=node("div","ps-3");body.append(children);
      const records=[];
      function add(v){
        if(records.length>=50)return;
        const child=build(v,depth+1), row=node("div","d-flex gap-2 align-items-start");
        child.el.classList.add("flex-grow-1");row.append(child.el);
        const item={child,row};
        if(type!=="not")row.append(btn(t("حذف","Remove"),()=>{row.remove();records.splice(records.indexOf(item),1);}));
        children.append(row);records.push(item);
      }
      if(type==="not")add(v.not||{});
      else{(v[type]||[{}]).forEach(add);body.append(btn(t("افزودن شرط","Add condition"),()=>add({})));}
      read=()=>{if(!records.length)throw new Error(t("حداقل یک شرط لازم است","At least one condition required"));return type==="not"?{not:records[0].child.read()}:{[type]:records.map(x=>x.child.read())};};
    }
    kind.addEventListener("change",()=>render({}));render(value);
    return {el:wrap,read:()=>read()};
  }
  try{
    const root=build(JSON.parse(hidden.value||"{}")||{},0);tree.append(root.el);
    form.addEventListener("submit",event=>{try{hidden.value=JSON.stringify(root.read());error.textContent="";}catch(e){event.preventDefault();error.textContent=e.message;}});
  }catch(e){error.textContent=e.message;form.addEventListener("submit",e=>e.preventDefault());}
})();
