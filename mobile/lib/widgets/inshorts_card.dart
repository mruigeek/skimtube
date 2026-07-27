import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:share_plus/share_plus.dart';
import 'package:provider/provider.dart';
import '../models/video.dart';
import '../providers/app_provider.dart';
import '../screens/settings_screen.dart';
import 'full_summary_modal.dart';

class InShortsCard extends StatelessWidget {
  final VideoModel video;

  const InShortsCard({Key? key, required this.video}) : super(key: key);

  void _openYouTubeUrl(String videoId) async {
    final uri = Uri.parse('https://www.youtube.com/watch?v=$videoId');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  void _shareSummary(BuildContext context) {
    final text = '📌 ${video.title}\n\n'
        '${video.shortSummary}\n\n'
        '📺 Watch video: https://www.youtube.com/watch?v=${video.videoId}\n\n'
        'Summarized by SkimTube';
    Share.share(text);
  }

  void _showFullSummaryModal(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => FullSummaryModal(videoId: video.videoId, fallbackVideo: video),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AppProvider>(context);
    final isSpeaking = provider.isPlayingTts && provider.currentlySpeakingVideoId == video.videoId;
    final size = MediaQuery.of(context).size;
    final thumbnailHeight = size.height * 0.42;

    return Container(
      color: Colors.white,
      child: Stack(
        children: [
          // ── Main Card Structure ──────────────────────────────────────────────
          Column(
            children: [
              // 1. Top Video Thumbnail Banner
              SizedBox(
                height: thumbnailHeight,
                width: double.infinity,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    CachedNetworkImage(
                      imageUrl: video.thumbnailUrl,
                      fit: BoxFit.cover,
                      placeholder: (context, url) => Container(
                        color: const Color(0xFF1E2530),
                        child: const Center(
                          child: CircularProgressIndicator(color: Color(0xFFFF3B30)),
                        ),
                      ),
                      errorWidget: (context, url, error) => Container(
                        color: const Color(0xFF1E2530),
                        child: const Icon(Icons.play_circle_outline, size: 64, color: Colors.white54),
                      ),
                    ),
                    // Top Gradient overlay
                    Positioned(
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 50,
                      child: Container(
                        decoration: const BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [Colors.black26, Colors.transparent],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // 2. White Summary Content Body
              Expanded(
                child: Container(
                  color: Colors.white,
                  padding: const EdgeInsets.fromLTRB(18, 16, 18, 56),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Channel Tag (Red logo icon + Channel Name)
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
                          Text(
                            video.channelName,
                            style: const TextStyle(
                              color: Color(0xFFE11D48), // Crisp branded red/pink
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              letterSpacing: -0.2,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),

                      // Title Headline (Bold Dark Text)
                      Text(
                        video.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFF111827), // Crisp dark charcoal
                          fontSize: 17.5,
                          fontWeight: FontWeight.w800,
                          height: 1.3,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Paragraph Body (Clean readable summary text)
                      Expanded(
                        child: SingleChildScrollView(
                          physics: const BouncingScrollPhysics(),
                          child: Text(
                            video.shortSummary,
                            style: const TextStyle(
                              color: Color(0xFF374151), // Clean dark body text
                              fontSize: 14.5,
                              height: 1.55,
                              fontWeight: FontWeight.w400,
                            ),
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
            top: thumbnailHeight - 22,
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
                    tooltip: 'Listen to summary',
                    onPressed: () => provider.speakShortSummary(video),
                    icon: Icon(
                      isSpeaking ? Icons.volume_up_rounded : Icons.volume_mute_rounded,
                      color: isSpeaking ? const Color(0xFF2563EB) : const Color(0xFF4B5563),
                      size: 20,
                    ),
                  ),
                  Container(height: 16, width: 1, color: Colors.black12),
                  // Bookmark Button
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                    padding: EdgeInsets.zero,
                    tooltip: 'Bookmark video',
                    onPressed: () => provider.toggleBookmark(video),
                    icon: Icon(
                      video.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                      color: video.isBookmarked ? const Color(0xFFFF9500) : const Color(0xFF4B5563),
                      size: 20,
                    ),
                  ),
                  Container(height: 16, width: 1, color: Colors.black12),
                  // Share Button
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                    padding: EdgeInsets.zero,
                    tooltip: 'Share summary',
                    onPressed: () => _shareSummary(context),
                    icon: const Icon(Icons.share_rounded, color: Color(0xFF4B5563), size: 19),
                  ),
                ],
              ),
            ),
          ),

          // ── Bottom Translucent Footer Overlay (Tap for full summary) ───────
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
              decoration: const BoxDecoration(
                color: Color(0xFF1E293B), // Deep slate footer
              ),
              child: SafeArea(
                top: false,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Tap for full summary trigger
                    Expanded(
                      child: InkWell(
                        onTap: () => _showFullSummaryModal(context),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Row(
                              children: [
                                Text(
                                  'Tap for Full Deep Digest',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 13.5,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                SizedBox(width: 4),
                                Icon(Icons.keyboard_arrow_up_rounded, color: Colors.white70, size: 18),
                              ],
                            ),
                            SizedBox(height: 2),
                            Text(
                              'View structured bullet takeaways & notes',
                              style: TextStyle(
                                color: Colors.white60,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Quick Actions: Watch YouTube & Settings
                    Row(
                      children: [
                        IconButton(
                          constraints: const BoxConstraints(),
                          padding: const EdgeInsets.all(4),
                          tooltip: 'Watch on YouTube',
                          icon: const Icon(Icons.play_circle_fill, color: Color(0xFFFF0000), size: 24),
                          onPressed: () => _openYouTubeUrl(video.videoId),
                        ),
                        const SizedBox(width: 6),
                        IconButton(
                          constraints: const BoxConstraints(),
                          padding: const EdgeInsets.all(4),
                          tooltip: 'Settings',
                          icon: const Icon(Icons.settings_rounded, color: Colors.white70, size: 20),
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(builder: (context) => const SettingsScreen()),
                            );
                          },
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
