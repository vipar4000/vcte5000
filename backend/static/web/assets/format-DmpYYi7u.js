function e(n){const t=Number(n);if(isNaN(t))return"0,00 EUR";const r=t.toFixed(2).split(".");return r[0].replace(/\B(?=(\d{3})+(?!\d))/g,".")+","+r[1]+" EUR"}export{e as f};
