import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:share_plus/share_plus.dart';
import 'package:provider/provider.dart';
import '../models/video.dart';
import '../providers/app_provider.dart';
import 'package:intl/intl.dart';
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


  String _formatPublishedAt(String publishedAtStr) {
    try {
      final DateTime dt = DateTime.parse(publishedAtStr);
      return DateFormat('dd MMM yyyy hh:mm a').format(dt);
    } catch (_) {
      return '';
    }
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

    return Container(
      color: Colors.white,
      child: LayoutBuilder(
        builder: (context, constraints) {
          // Native 16:9 aspect ratio calculation for clean 100% video thumbnail
          final thumbnailHeight = constraints.maxWidth * (9 / 16);

          return Stack(
            children: [
              // ── Main Card Structure ──────────────────────────────────────────────
              Column(
                children: [
                  // 1. Top Video Thumbnail Banner (Native 16:9 Clean Image)
                  SizedBox(
                    height: thumbnailHeight,
                    width: double.infinity,
                    child: Container(
                      color: const Color(0xFF0F141C),
                      child: CachedNetworkImage(
                        imageUrl: 'https://img.youtube.com/vi/${video.videoId}/mqdefault.jpg',
                        fit: BoxFit.cover,
                        alignment: Alignment.center,
                        placeholder: (context, url) => Container(
                          color: const Color(0xFF0F141C),
                          child: const Center(
                            child: CircularProgressIndicator(color: Color(0xFFFF3B30)),
                          ),
                        ),
                        errorWidget: (context, url, error) => Container(
                          color: const Color(0xFF0F141C),
                          child: const Icon(Icons.play_circle_outline, size: 64, color: Colors.white54),
                        ),
                      ),
                    ),
                  ),

                  // 2. White Summary Content Body
                  Expanded(
                    child: Container(
                      color: Colors.white,
                      padding: const EdgeInsets.fromLTRB(18, 20, 18, 56),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Channel Name & Tag
                          Row(
                            children: [
                              Container(
                                width: 14,
                                height: 14,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFF0000),
                                  borderRadius: BorderRadius.circular(3),
                                ),
                                child: const Icon(Icons.play_arrow_rounded, size: 10, color: Colors.white),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                video.channelName.toUpperCase(),
                                style: const TextStyle(
                                  color: Color(0xFFE11D48),
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 0.2,
                                ),
                              ),
                              if (video.publishedAt.isNotEmpty) ...[
                                const SizedBox(width: 6),
                                const Text(
                                  '•',
                                  style: TextStyle(color: Colors.black38, fontSize: 11),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  _formatPublishedAt(video.publishedAt),
                                  style: const TextStyle(
                                    color: Colors.black45,
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 8),

                          // Title Headline (Bold Dark Text)
                          Text(
                            video.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFF111827),
                              fontSize: 17.5,
                              fontWeight: FontWeight.w800,
                              height: 1.3,
                              letterSpacing: -0.3,
                            ),
                          ),
                          const SizedBox(height: 12),

                          // Paragraph Body (Clean readable summary text)
                          Expanded(
                            child: Text(
                              video.shortSummary,
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

              // ── Top-Right Action Tab (Bookmark & Share) ──────
              Positioned(
                top: thumbnailHeight - 29,
                right: 0,
                child: Container(
                  height: 29,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(12),
                      topRight: Radius.circular(12),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // TTS Volume Action
                      IconButton(
                        constraints: const BoxConstraints(),
                        padding: const EdgeInsets.symmetric(horizontal: 6),
                        iconSize: 18,
                        icon: Icon(
                          isSpeaking ? Icons.volume_up_rounded : Icons.volume_mute_rounded,
                          color: isSpeaking ? const Color(0xFF2563EB) : const Color(0xFF4B5563),
                        ),
                        onPressed: () => provider.speakShortSummary(video),
                      ),
                      // Bookmark Action
                      IconButton(
                        constraints: const BoxConstraints(),
                        padding: const EdgeInsets.symmetric(horizontal: 6),
                        iconSize: 18,
                        icon: Icon(
                          video.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                          color: video.isBookmarked ? const Color(0xFFFF9500) : const Color(0xFF4B5563),
                        ),
                        onPressed: () => provider.toggleBookmark(video),
                      ),
                      // Share Action
                      IconButton(
                        constraints: const BoxConstraints(),
                        padding: const EdgeInsets.symmetric(horizontal: 6),
                        iconSize: 17,
                        icon: const Icon(Icons.share_rounded, color: Color(0xFF4B5563)),
                        onPressed: () => _shareSummary(context),
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
                    color: Color(0xFF1E293B),
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
                               onPressed: () async {
                                 await Navigator.push(
                                   context,
                                   MaterialPageRoute(builder: (context) => const SettingsScreen()),
                                 );
                                 if (context.mounted) {
                                   Provider.of<AppProvider>(context, listen: false).refreshFeed();
                                 }
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
          );
        },
      ),
    );
  }
}
