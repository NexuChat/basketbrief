"""Conservative source checks for the demo's English/Arabic field formats.

These checks narrow accepted interpretations; they do not prove OCR fidelity or
physical events. Unrecognized phrasing requires contributor clarification.
"""
import re
from decimal import Decimal

DIGITS=str.maketrans('٠١٢٣٤٥٦٧٨٩٫٬','0123456789.,')
NUMBER=r'\d+(?:,\d{3})*(?:\.\d+)?'
NEGATIVE=re.compile(r"\b(?:not|never|no|haven't|didn't|wasn't|weren't|cannot|can't|unknown)\b|لم\s|ليس|ليست|غير\s",re.I)


def normal(text):
    return text.translate(DIGITS).lower()


def expense_amounts(text):
    """Explicit totals take precedence over currency-tagged amounts/unit prices."""
    text=normal(text)
    totals=[]
    for m in re.finditer(rf'(?<![a-z])(?:printed\s+|grand\s+)?(?:total|الإجمالي|الاجمالي|المجموع)\s*[:=]?\s*(?:usd\s*|\$\s*)?({NUMBER})',text):
        prefix=text[max(0,m.start()-20):m.start()]
        if not NEGATIVE.search(prefix):totals.append(Decimal(m[1].replace(',','')))
    if totals:return set(totals)
    tagged=[]
    for m in re.finditer(rf'(?:\busd\s*|\$\s*)({NUMBER})|({NUMBER})\s*(?:usd\b|دولار)',text):
        if not NEGATIVE.search(text[max(0,m.start()-16):m.start()]):
            tagged.append(Decimal((m[1] or m[2]).replace(',','')))
    return set(tagged)


VERBS={
 'loaded':r'(?:loaded|حمّلنا|حملنا|تحميل)',
 'delivered':r'(?:delivered|distributed|سلّمنا|سلمنا|وزعنا|تم\s+تسليم|مسلّمة|مسلمة)',
 'returned':r'(?:returned|رجعت|أرجعنا|ارجعنا|مرتجعة|مرتجع)',
 'households':r'(?:unique\s+households?|households?|families|أسر|اسر|عائلات)',
}


def field_values(text, field):
    text=normal(text)
    verb=VERBS[field]
    unit=r'(?:(?:kits?|baskets?|parcels?|طرود|طرد|سلال|سلة)\s+)?' if field!='households' else ''
    filler=r'(?:(?:were|was|actually|successfully|have\s+been|تم)\s+)?' if field!='households' else ''
    patterns=[rf'(?<![\w.])(?P<number>\d+)\s+{unit}{filler}{verb}\b',
              rf'\b{verb}\s+(?:kits?|baskets?|parcels?|طرود|طرد|سلال|سلة)\s*[:=]\s*(?P<number>\d+)(?!\d)',
              rf'\b{verb}\s*[:=]?\s*(?P<number>\d+)(?!\d)']
    values=set()
    for pattern in patterns:
        for m in re.finditer(pattern,text):
            # Restrict negation to the current clause; a later denial of the old
            # value must not erase an earlier positive correction.
            prefix=re.split(r'[.;\n,!؟،]',text[:m.start()])[-1][-55:]
            suffix=text[m.end():m.end()+35]
            if NEGATIVE.search(prefix) or NEGATIVE.search(m[0]):continue
            if re.match(r'\s*(?:was|were|is|are)\s+(?:incorrect|wrong|mistaken)',suffix):continue
            values.add(int(m['number']))
    return values
