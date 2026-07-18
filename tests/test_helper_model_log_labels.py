import unittest

import hybrid_translate as ht


class HelperModelLogLabelsTest(unittest.TestCase):
    def test_deepseek_analysis_log_label_does_not_say_minimax(self):
        label = ht._helper_model_log_name("https://api.deepseek.com", "deepseek-v4-flash")

        self.assertEqual(label, "DeepSeek V4 Flash")
        self.assertNotIn("MiniMax", label)

    def test_minimax_analysis_log_label_uses_selected_model(self):
        label = ht._helper_model_log_name("https://api.minimax.io/v1", "MiniMax-M2.7")

        self.assertEqual(label, "MiniMax-M2.7")

    def test_opencode_go_minimax_log_label_resolves_label(self):
        label = ht._helper_model_log_name("https://opencode.ai/zen/go/v1/messages", "minimax-m3")

        self.assertEqual(label, "MiniMax M3 (OpenCode Go)")

    def test_opencode_go_glm52_log_label_resolves_label(self):
        label = ht._helper_model_log_name("https://opencode.ai/zen/go/v1", "glm-5.2")

        self.assertEqual(label, "GLM-5.2 (OpenCode Go)")

    def test_opencode_go_qwen37_max_log_label_resolves_label(self):
        label = ht._helper_model_log_name("https://opencode.ai/zen/go/v1/messages", "qwen3.7-max")

        self.assertEqual(label, "Qwen3.7 Max (OpenCode Go)")

    def test_bedrock_analysis_log_label_resolves_label(self):
        label = ht._helper_model_log_name("https://bedrock.dummy", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.assertEqual(label, "Bedrock Claude 3.5 Sonnet")

        label46 = ht._helper_model_log_name("https://bedrock.dummy", "anthropic.claude-sonnet-4-6")
        self.assertEqual(label46, "Bedrock Claude 4.6 Sonnet")

        label_llama = ht._helper_model_log_name("https://bedrock.dummy", "meta.llama3-3-70b-instruct-v1:0")
        self.assertEqual(label_llama, "Bedrock Llama 3.3 70B")

    def test_gemini_analysis_log_label_resolves_label(self):
        label35 = ht._helper_model_log_name("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-3.5-flash")
        self.assertEqual(label35, "Gemini 3.5 Flash")

        label25 = ht._helper_model_log_name("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash")
        self.assertEqual(label25, "Gemini 2.5 Flash")


if __name__ == "__main__":
    unittest.main()
