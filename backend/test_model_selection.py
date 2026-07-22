#!/usr/bin/env python3
"""
Simple test for the model selection logic
"""

import sys
import os

# Add the current directory and app to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(current_dir, 'app')
sys.path.insert(0, current_dir)
sys.path.insert(0, app_path)

try:
    from services.llm_gateway import _LLMGateway
    print("Successfully imported _LLMGateway")
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    # Try to list what's available
    print(f"Contents of current directory: {os.listdir('.')}")
    if os.path.exists('app'):
        print(f"Contents of app/: {os.listdir('app')}")
        if os.path.exists('app/services'):
            print(f"Contents of app/services/: {os.listdir('app/services')}")
    sys.exit(1)

def test_model_selection():
    """Test the model selection logic with various inputs"""
    
    # Create a mock LLM gateway instance
    gateway = _LLMGateway()
    
    test_cases = [
        # Should use SONNET (regular chat)
        ("allo", False, "Simple greeting"),
        ("chào bạn", False, "Vietnamese greeting"),
        ("hôm nay thứ mấy?", False, "Simple date question"),
        ("bạn có khỏe không?", False, "Simple health check"),
        ("cảm ơn bạn", False, "Thank you"),
        ("thời tiết hôm nay sao?", False, "Weather question"),
        ("tbh", False, "Very short"),
        ("ok", False, "Acknowledgment"),
        
        # Should use OPUS (code, writing, complex)
        ("viết hàm tính fibonacci", True, "Code writing request"),
        ("giúp tôi debug lỗi này: const x = 5;", True, "Code debugging"),
        ("tạo một class Python để quản lý danh sách học sinh", True, "Class creation"),
        ("viết bài phân tích Truyện Kiều", True, "Essay writing request"),
        ("so sánh hai cách tính thuế thu nhập cá nhân", True, "Comparison request"),
        ("giải thích tại sao trời xanh", True, "Explanation request"),
        ("làm sao để học tiếng Pháp hiệu quả?", True, "Language learning advice"),
        ("chứng minh rằng tổng của các góc trong tam giác là 180 độ", True, "Proof request"),
        ("tóm tắt nội dung của bài đọc này", True, "Summarizing request"),
        
        # Edge cases - longer messages should lean toward OPUS
        ("a" * 350, True, "Very long message (350 chars)"),
        
        # Mixed cases
        ("chào bạn, hôm nay tôi muốn viết một hàm để tính giai thừa", True, "Greeting + code request"),
    ]
    
    print("Testing model selection logic:")
    print("=" * 50)
    
    all_passed = True
    for message, expected_is_opus, description in test_cases:
        # Test the _should_use_opus method directly
        is_opus = gateway._should_use_opus(message)
        status = "✓ PASS" if is_opus == expected_is_opus else "✗ FAIL"
        if is_opus != expected_is_opus:
            all_passed = False
        
        print(f"{status} | {description}")
        print(f"      Message: \"{message[:50]}{'...' if len(message) > 50 else ''}\"")
        print(f"      Expected: {'OPUS' if expected_is_opus else 'SONNET'}, Got: {'OPUS' if is_opus else 'SONNET'}")
        print()
    
    print("=" * 50)
    if all_passed:
        print("All tests PASSED! 🎉")
    else:
        print("Some tests FAILED! ❌")
    
    return all_passed

if __name__ == "__main__":
    success = test_model_selection()
    sys.exit(0 if success else 1)