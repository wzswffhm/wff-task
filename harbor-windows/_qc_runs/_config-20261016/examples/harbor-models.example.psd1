@{
    Profiles = @{
        qwen_3_8_max = @{
            Model   = '<qwen-model-id>'
            ApiKey  = '<replace-with-real-qwen-key>'
            Agent   = 'windows-claude-code'
            BaseUrl = '<qwen-anthropic-compatible-endpoint>'
        }
        claude_opus_5 = @{
            Model   = '<claude-model-id>'
            ApiKey  = '<replace-with-real-claude-key>'
            Agent   = 'windows-claude-code'
            BaseUrl = '<claude-anthropic-compatible-endpoint>'
        }
    }
}
