export const parseT = (t: number) => {
    const h = Math.floor(t / (60 * 60));
    t -= h * 60 * 60;
    const m = Math.floor(t / 60);
    t -= m * 60;
    const s = t;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// 保留小数点后n位
export const round = (num: number, n: number) => {
    return Math.round(num * Math.pow(10, n)) / Math.pow(10, n);
}

export const round4 = (num: number) => {
    return round(num, 4);
}

export const round2 = (num: number) => {
    return round(num, 2);
}
