class ProgressBar:
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """

    def __init__(
        self,
        iteration,
        total,
        prefix="",
        suffix="",
        decimals=1,
        length=100,
        fill="█",
        print_end="\r",
    ):
        self.iteration = iteration
        self.total = total
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = decimals
        self.length = length
        self.fill = fill
        self.print_end = print_end
        self.percent = ("{0:." + str(decimals) + "f}").format(
            100 * (iteration / float(total))
        )
        self.bar_string = None
        self.update_bar()

    def update_bar(
        self,
        new_iteration=None,
        new_prefix=None,
        new_suffix=None,
        percentage: bool = True,
    ):
        if new_iteration is None:
            new_iteration = self.iteration
        if new_prefix is not None:
            self.prefix = new_prefix
        if new_suffix is not None:
            self.suffix = new_suffix
        filledLength = int(self.length * new_iteration // self.total)
        if percentage is False:
            self.percent = ""
        else:
            self.percent = ("{0:." + str(self.decimals) + "f}").format(
                100 * (new_iteration / float(self.total))
            )
        bar = self.fill * filledLength + "-" * (self.length - filledLength)
        self.bar_string = f"\r{self.prefix} |{bar}| {self.percent}% {self.suffix}"
        return self.bar_string