def safe_lower(text):
    """
    안전하게 문자열을 소문자로 변환합니다.
    None, 숫자, 불린 등 모든 타입을 안전하게 처리합니다.
    
    Args:
        text: 변환할 텍스트 (모든 타입 가능)
    
    Returns:
        str: 소문자로 변환된 문자열, None인 경우 빈 문자열
    """
    if text is None:
        return ""
    elif isinstance(text, str):
        return text.lower()
    else:
        return str(text).lower()

def safe_str(text, default=""):
    """
    안전하게 문자열로 변환합니다.
    
    Args:
        text: 변환할 값
        default: None인 경우 반환할 기본값
    
    Returns:
        str: 문자열로 변환된 값
    """
    if text is None:
        return default
    else:
        return str(text)

def safe_get(dictionary, key, default=""):
    """
    딕셔너리에서 안전하게 값을 가져와서 문자열로 변환합니다.
    
    Args:
        dictionary: 딕셔너리
        key: 키
        default: 기본값
    
    Returns:
        str: 안전하게 변환된 문자열
    """
    value = dictionary.get(key, default)
    return safe_str(value, default)
