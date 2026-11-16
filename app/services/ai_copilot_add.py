with open('D:\\\\iNew\\\\app\\\\services\\\\ai_copilot.py', 'r') as f:
    lines = f.readlines()
    # Find the end of the _call_llm_detailed method
    insert_pos = -1
    for i, line in enumerate(lines):
        if 'def _call_llm_detailed' in line:
            # Find the end of this method
            j = i
            while j < len(lines) and (not lines[j].strip().startswith('def ') and not lines[j].strip().startswith('class ')):
                j += 1
            insert_pos = j
            break
    
    if insert_pos != -1:
        # Insert new methods after _call_llm_detailed
        new_lines = [
            '\n',
            '    @staticmethod\n',
            '    def _topic_id_for_post(self, post_id: int) -> Optional[int]:\n',
            '        \"\"\"Get topic ID associated with a post\"\"\"\n',
            '        post = db.query(RawPost).filter(RawPost.id == post_id).first()\n',
            '        if post and post.source_channel_id:\n',
            '            channel = db.query(SourceChannel).filter(SourceChannel.id == post.source_channel_id).first()\n',
            '            if channel and hasattr(channel, \"topic_sources\") and channel.topic_sources:\n',
            '                return channel.topic_sources[0].topic_id\n',
            '        return None\n',
            '\n',
            '    @staticmethod\n',
            '    def i_usage_today() -> dict:\n',
            '        \"\"\"Get today\'s AI usage statistics\"\"\"\n',
            '        today = datetime.utcnow().date()\n',
            '        usage = db.query(AiUsageLog).filter(AiUsageLog.created_at >= datetime.combine(today, datetime.min.time())).all()\n',
            '        total_tokens = sum(log.tokens_used for log in usage) if usage else 0\n',
            '        return {\n',
            '            \"date\": str(today),\n',
            '            \"total_tokens\": total_tokens,\n',
            '            \"count\": len(usage),\n',
            '            \"average_tokens\": total_tokens / len(usage) if usage else 0\n',
            '        }\n',
            '\n'
        ]
        lines[insert_pos:] = new_lines
        with open('D:\\\\iNew\\\\app\\\\services\\\\ai_copilot.py', 'w') as f:
            f.writelines(lines)