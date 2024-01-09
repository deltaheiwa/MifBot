

def telegram_command(func):
    func.is_command = True
    return func
