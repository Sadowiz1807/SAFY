from pathlib import Path
OUT=Path('Reports/verification/2026-06-30_suspicious_areas_prefix_verification')
E=OUT/'evidence'
shot=r'C:\Users\ASUS\AppData\Local\hermes\cache\screenshots\browser_screenshot_ae5ec518386b4d968d55e626c897ee57.png'
(E/'ui_visible_message.txt').write_text(f"Browser workflow F1: logged in to http://127.0.0.1:8000/dashboard as tester/sadowiz flow, sent message 'chào bạn'. Visible UI response was: 'Safy backend returned an empty agent response.' Screenshot: {shot}\n",encoding='utf-8')
(E/'ui_chat_network_response.json').write_text('{\n  "browser_screenshot": "'+shot.replace('\\','\\\\')+'",\n  "visible_user_message": "chào bạn",\n  "visible_agent_message": "Safy backend returned an empty agent response.",\n  "classification": "FRONTEND_CHAT_RENDER_FALLBACK / backend empty content"\n}\n',encoding='utf-8')
# Append UI details to report
p=OUT/'07_UI_RENDER_VERIFICATION.md'
text=p.read_text(encoding='utf-8') if p.exists() else '# UI Render Verification\n'
text += f"\n## Browser F1 chat verification\n\n- User input: `chào bạn`\n- Visible result: `Safy backend returned an empty agent response.`\n- Screenshot: `{shot}`\n- Status: FAIL for UI-003 / chat visible behavior.\n- Root cause: frontend fallback is triggered because backend chat path does not return useful assistant content/error.\n"
p.write_text(text,encoding='utf-8')
print(shot)
