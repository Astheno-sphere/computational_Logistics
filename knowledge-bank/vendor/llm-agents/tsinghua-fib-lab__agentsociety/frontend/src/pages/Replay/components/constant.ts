// // 智能体教育等级
// enum Education {
//     // 未指定
//     EDUCATION_UNSPECIFIED = 0;
//     // 博士
//     EDUCATION_DOCTOR = 1;
//     // 硕士
//     EDUCATION_MASTER = 2;
//     // 本科
//     EDUCATION_BACHELOR = 3;
//     // 高中
//     EDUCATION_HIGH_SCHOOL = 4;
//     // 初中
//     EDUCATION_JUNIOR_HIGH_SCHOOL = 5;
//     // 小学
//     EDUCATION_PRIMARY_SCHOOL = 6;
//     // 大专
//     EDUCATION_COLLEGE = 7;
// }
export const PairEducation = [
    [1, "博士"],
    [2, "硕士"],
    [3, "本科"],
    [4, "高中"],
    [5, "初中"],
    [6, "小学"],
    [7, "大专"],
]
export const MapEducation = new Map<number, string>(PairEducation as Iterable<readonly [number, string]>);

// // 智能体性别
// enum Gender {
//     // 未指定
//     GENDER_UNSPECIFIED = 0;
//     // 男性
//     GENDER_MALE = 1;
//     // 女性
//     GENDER_FEMALE = 2;
// }
export const PairGender = [
    [1, "男性"],
    [2, "女性"],
]
export const MapGender = new Map<number, string>(PairGender as Iterable<readonly [number, string]>);

// // 智能体消费水平
// enum Consumption {
//     // 未指定
//     CONSUMPTION_UNSPECIFIED = 0;
//     // 低
//     CONSUMPTION_LOW = 1;
//     // 较低
//     CONSUMPTION_RELATIVELY_LOW = 2;
//     // 中等
//     CONSUMPTION_MEDIUM = 3;
//     // 较高
//     CONSUMPTION_RELATIVELY_HIGH = 4;
//     // 高
//     CONSUMPTION_HIGH = 5;
// }
export const PairConsumption = [
    [1, "低"],
    [2, "较低"],
    [3, "中等"],
    [4, "较高"],
    [5, "高"],
];
export const MapConsumption = new Map<number, string>(PairConsumption as Iterable<readonly [number, string]>);

export const PairLandUse = [
    [0, '未指定'],
    [5, '商服用地'],
    [6, '工矿仓储用地'],
    [7, '住宅用地'],
    [8, '公共管理与公共服务用地'],
    [10, '交通运输用地'],
    [12, '其他土地'],
];
export const MapLandUse = new Map<number, string>(PairLandUse as Iterable<readonly [number, string]>);

export const GetEducationName = (education: number) => {
    return MapEducation.get(education) || "未知";
}

export const GetGenderName = (gender: number) => {
    return MapGender.get(gender) || "未知";
}

export const GetConsumptionName = (consumption: number) => {
    return MapConsumption.get(consumption) || "未知";
}

export const GetLandUseName = (landUse: number) => {
    return MapLandUse.get(landUse) || "未知";
}
