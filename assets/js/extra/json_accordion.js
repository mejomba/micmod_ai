function initJsonAccordion(data) {
    // ایجاد container اصلی
    const container = document.createElement("div");
    container.id = "json-container";
    container.className = "accordion-container";
    container.style.position = "fixed";
    container.style.top = "10px";
    container.style.left = "10px";
    container.style.right = "10px";
    container.style.maxHeight = "90vh";
    container.style.overflowY = "auto";
    container.style.background = "#fff";
    container.style.padding = "10px";
    container.style.borderRadius = "8px";
    container.style.boxShadow = "0 4px 10px rgba(0,0,0,0.1)";
    container.style.zIndex = "9999";
    container.style.direction = "ltr"; // برای ساختار JSON انگلیسی

    // ایجاد باکس جستجو
    const searchBox = document.createElement("input");
    searchBox.type = "text";
    searchBox.id = "search-box";
    searchBox.className = "search-box";
    searchBox.placeholder = "🔍 جستجو در داده‌ها...";
    searchBox.style.width = "100%";
    searchBox.style.marginBottom = "10px";
    searchBox.style.padding = "8px";
    searchBox.style.border = "1px solid #ccc";
    searchBox.style.borderRadius = "6px";

    container.appendChild(searchBox);

    // ایجاد محل نمایش اکاردئون
    const accordionWrapper = document.createElement("div");
    accordionWrapper.id = "accordion-content";
    container.appendChild(accordionWrapper);

    document.body.appendChild(container);

    // تابع ساخت اکاردئون
    function createAccordion(data, parentElement, level = 0) {
        for (const [key, value] of Object.entries(data)) {
            const item = document.createElement("div");
            item.className = "accordion-item";
            item.style.marginLeft = `${level * 10}px`;

            const header = document.createElement("div");
            header.className = "accordion-header";
            header.textContent = key;
            header.style.cursor = "pointer";
            header.style.padding = "5px 8px";
            header.style.border = "1px solid #ddd";
            header.style.borderRadius = "6px";
            header.style.marginBottom = "4px";
            header.style.background = "#f7f7f7";
            header.style.fontWeight = "bold";
            header.addEventListener("mouseenter", () => header.style.background = "#eaeaea");
            header.addEventListener("mouseleave", () => header.style.background = "#f7f7f7");

            const content = document.createElement("div");
            content.className = "accordion-content";
            content.style.display = "none";
            content.style.padding = "6px 10px";
            content.style.marginLeft = "10px";
            content.style.borderLeft = "2px solid #ddd";

            header.addEventListener("click", () => {
                content.style.display = content.style.display === "none" ? "block" : "none";
            });

            if (typeof value === "object" && value !== null) {
                if (Array.isArray(value)) {
                    value.forEach((val, i) => {
                        const arrayItem = document.createElement("div");
                        arrayItem.textContent = `[${i}]`;
                        content.appendChild(arrayItem);
                        if (typeof val === "object" && val !== null)
                            createAccordion(val, arrayItem, level + 1);
                        else
                            arrayItem.textContent += `: ${val}`;
                    });
                } else {
                    createAccordion(value, content, level + 1);
                }
            } else {
                const textNode = document.createElement("div");
                textNode.textContent = `${key}: ${value}`;
                content.appendChild(textNode);
            }

            item.appendChild(header);
            item.appendChild(content);
            parentElement.appendChild(item);
        }
    }

    // ایجاد اکاردئون از داده
    createAccordion(data, accordionWrapper);

    // افزودن قابلیت جستجو
    searchBox.addEventListener("input", () => {
    const query = searchBox.value.toLowerCase();

    function searchAndFilter(element) {
        if (!element) return false;

        let matched = false;

        // پیدا کردن همه‌ی آیتم‌های سطح فعلی
        const items = element.querySelectorAll(":scope > .accordion-item");

        items.forEach(item => {
            const header = item.querySelector(":scope > .accordion-header");
            const content = item.querySelector(":scope > .accordion-content");

            const headerText = header.textContent.toLowerCase();
            const isHeaderMatch = headerText.includes(query);

            // فراخوانی بازگشتی برای تمام زیرمجموعه‌ها
            const childMatched = searchAndFilter(content);

            if (isHeaderMatch || childMatched) {
                item.style.display = "block";
                matched = true;

                // وقتی چیزی جستجو میشه، محتواهای منطبق باز می‌مونن
                if (query) content.style.color = 'red'// content.style.display = "block";
            } else {
                item.style.display = "block";
            }
        });

        return matched;
    }

    searchAndFilter(accordionWrapper);
});

}
