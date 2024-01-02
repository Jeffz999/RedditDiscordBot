import random

def get_response(message:str) -> str:
    p_message = message.lower() 
    
    if p_message == 'hello':
        return "HELLO"
    
    if p_message == 'roll':
        return str(random.randint(1, 6))
    
    if p_message == 'who are you?':
        return "Do you 2 piss ants not have a clue who I am?\nSeriously\nI am Alek Fucking Rawls. I am the founder of Republic of Texas Airsoft\n\nI am not some speedsofter to shit on"

    if p_message == 'help':
        return "ask hello, roll, who are you?\n Reddit functionality coming soon"
    
    return "wtf do u mean?"