import enum


class TimestampFormats(enum.Enum):
    """
    Markdown postfixes for timestamp formats
        SHORT_DATE: 1/1/2021 \n
        LONG_DATE: Friday, January 1, 2021, \n
        SHORT_TIME: 12:00 AM \n
        LONG_TIME: 12:00:00 AM \n
        SHORT_DATE_TIME: 1/1/2021 12:00 AM \n
        LONG_DATE_TIME: Friday, January 1, 2021 12:00 AM \n
        RELATIVE_TIME: 1 day ago \n
    """

    SHORT_DATE = "d"
    LONG_DATE = "D"
    SHORT_TIME = "t"
    LONG_TIME = "T"
    SHORT_DATE_TIME = "f"
    LONG_DATE_TIME = "F"
    RELATIVE_TIME = "R"
