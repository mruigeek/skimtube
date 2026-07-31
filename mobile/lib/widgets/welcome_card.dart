import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:share_plus/share_plus.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../screens/settings_screen.dart';

class WelcomeCard extends StatefulWidget {
  const WelcomeCard({Key? key}) : super(key: key);

  @override
  State<WelcomeCard> createState() => _WelcomeCardState();
}

class _WelcomeCardState extends State<WelcomeCard> {
  final FlutterTts _tts = FlutterTts();
  bool _isSpeaking = false;

  final String _welcomeTitle = "Welcome to SkimTube — AI Byte-Sized Video Digests";
  final String _welcomeBody =
      "SkimTube automatically monitors your favorite YouTube channels, extracts transcripts, and generates crisp 100-word summaries and structured key takeaways powered by AI.\n\nNever miss out on key technical insights, breaking news, or channel updates. Tap the button below to add your favorite YouTube channels and start generating your daily personalized feed.";

  void _toggleTts() async {
    if (_isSpeaking) {
      await _tts.stop();
      if (mounted) setState(() => _isSpeaking = false);
    } else {
      setState(() => _isSpeaking = true);
      _tts.setCompletionHandler(() {
        if (mounted) setState(() => _isSpeaking = false);
      });
      await _tts.speak("$_welcomeTitle. $_welcomeBody");
    }
  }

  void _shareApp() {
    Share.share(
      '📌 SkimTube — Byte-Sized YouTube Video Summaries powered by AI.\nGet daily video digests in seconds!',
    );
  }

  @override
  void dispose() {
    _tts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final bannerHeight = constraints.maxWidth * (9 / 16);

          return Stack(
            children: [
              // ── Main Card Structure ──────────────────────────────────────────────
              Column(
                children: [
                  // 1. Top Welcome Banner (16:9 Hero Container with SkimTube Logo)
                  SizedBox(
                    height: bannerHeight,
                    width: double.infinity,
                    child: Container(
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            Color(0xFF0F141C),
                            Color(0xFF1E2634),
                            Color(0xFF111827),
                          ],
                        ),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFF2563EB).withValues(alpha: 0.4),
                                  blurRadius: 20,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: ClipOval(
                              child: Image.asset(
                                'assets/logo.png',
                                width: 72,
                                height: 72,
                                fit: BoxFit.cover,
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            'skimtube',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                              letterSpacing: -0.8,
                            ),
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            'Instant Daily Video Digests',
                            style: TextStyle(
                              color: Colors.white60,
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // 2. White Summary Content Body
                  Expanded(
                    child: Container(
                      color: Colors.white,
                      padding: const EdgeInsets.fromLTRB(18, 16, 18, 64),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Channel Tag (Official Badge)
                          Row(
                            children: [
                              Container(
                                width: 18,
                                height: 18,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFF0000),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Icon(Icons.play_arrow_rounded, size: 14, color: Colors.white),
                              ),
                              const SizedBox(width: 8),
                              const Text(
                                'SkimTube Official',
                                style: TextStyle(
                                  color: Color(0xFFE11D48),
                                  fontSize: 13,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: -0.2,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),

                          // Title Headline
                          Text(
                            _welcomeTitle,
                            style: const TextStyle(
                              color: Color(0xFF111827),
                              fontSize: 17.5,
                              fontWeight: FontWeight.w800,
                              height: 1.3,
                              letterSpacing: -0.3,
                            ),
                          ),
                          const SizedBox(height: 12),

                          // Paragraph Body
                          Expanded(
                            child: Text(
                              _welcomeBody,
                              style: const TextStyle(
                                color: Color(0xFF374151),
                                fontSize: 14.5,
                                height: 1.55,
                                fontWeight: FontWeight.w400,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),

              // ── Floating Action Capsule Pill (Overlapping Image Bottom-Right) ───
              Positioned(
                top: bannerHeight - 22,
                right: 16,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: const [
                      BoxShadow(
                        color: Colors.black26,
                        blurRadius: 10,
                        offset: Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // TTS Audio Button
                      IconButton(
                        constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                        padding: EdgeInsets.zero,
                        tooltip: 'Listen to welcome message',
                        onPressed: _toggleTts,
                        icon: Icon(
                          _isSpeaking ? Icons.volume_up_rounded : Icons.volume_mute_rounded,
                          color: _isSpeaking ? const Color(0xFF2563EB) : const Color(0xFF4B5563),
                          size: 20,
                        ),
                      ),
                      Container(height: 16, width: 1, color: Colors.black12),
                      // Share Button
                      IconButton(
                        constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                        padding: EdgeInsets.zero,
                        tooltip: 'Share SkimTube',
                        onPressed: _shareApp,
                        icon: const Icon(Icons.share_rounded, color: Color(0xFF4B5563), size: 19),
                      ),
                    ],
                  ),
                ),
              ),

              // ── Bottom Call-To-Action Footer Bar (Navigate to Settings / Add Channel) ───
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: const BoxDecoration(
                    color: Color(0xFF1E293B),
                  ),
                  child: SafeArea(
                    top: false,
                    child: SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: () async {
                          await Navigator.push(
                            context,
                            MaterialPageRoute(builder: (context) => const SettingsScreen()),
                          );
                          if (context.mounted) {
                            Provider.of<AppProvider>(context, listen: false).refreshFeed();
                          }
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF2563EB), // Royal Blue
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          elevation: 2,
                        ),
                        icon: const Icon(Icons.add_circle_outline_rounded, size: 20),
                        label: const Text(
                          'Set Up Feed — Add Channels',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
