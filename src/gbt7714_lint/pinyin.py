"""Pinyin surname detection.

GB/T 7714-2025 keeps Chinese pinyin surnames in ALL CAPS (e.g. ``ZHANG S Q``)
while foreign surnames changed from ALL CAPS (2015) to initial-caps only
(2025, e.g. ``Einstein A``). To avoid "fixing" pinyin surnames, an ALL-CAPS
surname that matches a known pinyin surname romanization is left alone.

The list covers the standard romanizations of common Chinese surnames plus
frequent Hong Kong / Taiwan / overseas spellings. Matching is conservative:
false positives only suppress an auto-fix, never corrupt text.
"""

# Mainland pinyin surnames (single-syllable and compound)
_PINYIN_SURNAMES = {
    "AI", "AN", "AO", "BA", "BAI", "BAN", "BAO", "BEI", "BI", "BIAN", "BIN",
    "BING", "BO", "BU", "CAI", "CAO", "CEN", "CHAI", "CHAN", "CHANG", "CHAO",
    "CHE", "CHEN", "CHENG", "CHI", "CHONG", "CHU", "CI", "CONG", "CUI", "DA",
    "DAI", "DAN", "DANG", "DAO", "DENG", "DI", "DIAO", "DING", "DONG", "DOU",
    "DU", "DUAN", "E", "FAN", "FANG", "FEI", "FENG", "FU", "GAN", "GANG",
    "GAO", "GE", "GENG", "GONG", "GOU", "GU", "GUAN", "GUANG", "GUI", "GUO",
    "HA", "HAI", "HAN", "HANG", "HAO", "HE", "HENG", "HONG", "HOU", "HU",
    "HUA", "HUAI", "HUAN", "HUANG", "HUI", "HUO", "JI", "JIA", "JIAN",
    "JIANG", "JIAO", "JIE", "JIN", "JING", "JIU", "JU", "JUAN", "JUE", "JUN",
    "KANG", "KE", "KONG", "KOU", "KUANG", "KUI", "LAI", "LAN", "LANG", "LAO",
    "LE", "LEI", "LENG", "LI", "LIAN", "LIANG", "LIAO", "LIN", "LING", "LIU",
    "LONG", "LOU", "LU", "LUAN", "LUO", "LV", "LYU", "MA", "MAI", "MAN",
    "MAO", "MEI", "MENG", "MI", "MIAO", "MIN", "MING", "MO", "MOU", "MU",
    "NA", "NAN", "NIAN", "NIE", "NING", "NIU", "NONG", "OU", "PAN", "PANG",
    "PEI", "PENG", "PI", "PIAO", "PING", "PU", "QI", "QIAN", "QIANG", "QIAO",
    "QIN", "QING", "QIU", "QU", "QUAN", "RAN", "RAO", "REN", "RONG", "RU",
    "RUAN", "RUI", "SA", "SAI", "SANG", "SHA", "SHAN", "SHANG", "SHAO",
    "SHE", "SHEN", "SHENG", "SHI", "SHU", "SHUAI", "SHUANG", "SHUI", "SI",
    "SONG", "SU", "SUI", "SUN", "TAN", "TANG", "TAO", "TENG", "TIAN", "TONG",
    "TU", "WAN", "WANG", "WEI", "WEN", "WENG", "WU", "XI", "XIA", "XIAN",
    "XIANG", "XIAO", "XIE", "XIN", "XING", "XIONG", "XU", "XUAN", "XUE",
    "YAN", "YANG", "YAO", "YE", "YI", "YIN", "YING", "YONG", "YOU", "YU",
    "YUAN", "YUE", "YUN", "ZAN", "ZANG", "ZENG", "ZHA", "ZHAI", "ZHAN",
    "ZHANG", "ZHAO", "ZHE", "ZHEN", "ZHENG", "ZHI", "ZHONG", "ZHOU", "ZHU",
    "ZHUANG", "ZHUO", "ZI", "ZOU", "ZU", "ZUO",
    # Compound surnames
    "OUYANG", "SIMA", "ZHUGE", "SITU", "XIAHOU", "HUANGFU", "SHANGGUAN",
    "DONGFANG", "DUANMU", "GONGSUN", "LINGHU", "MURONG", "NALAN", "WEISHENG",
}

# Common Hong Kong / Taiwan / overseas romanizations
_HKTW_SURNAMES = {
    "CHAN", "CHEUNG", "CHOW", "CHOI", "CHU", "FUNG", "HO", "HUI", "IP",
    "KWAN", "KWOK", "KWONG", "LAM", "LAU", "LEE", "LEUNG", "LO", "LOK",
    "MAK", "NG", "PANG", "POON", "SIU", "SO", "SZE", "TAM", "TANG", "TSANG",
    "TSE", "TSUI", "WONG", "YEUNG", "YIP", "YUEN",
    "CHIU", "HSIAO", "HSIEH", "HSU", "HUNG", "KAO", "KUO", "LIN", "SOONG",
    "TSAI", "TSENG", "WEI", "YEH",
}

PINYIN_SURNAMES = _PINYIN_SURNAMES | _HKTW_SURNAMES


def is_pinyin_surname(word: str) -> bool:
    """True if an ALL-CAPS word is plausibly a romanized Chinese surname."""
    return word.upper() in PINYIN_SURNAMES
