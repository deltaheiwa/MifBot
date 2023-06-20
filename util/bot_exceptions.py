class BattleMissingArgumentsError(Exception):
    def __init__(self, value, argument, message=f"Missing valid value for argument. Check documentation for more details."):
        self.argument = argument
        self.value = value
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.argument}: {self.value} -> {self.message}'