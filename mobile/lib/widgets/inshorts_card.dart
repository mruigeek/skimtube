import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:share_plus/share_plus.dart';
import 'package:provider/provider.dart';
import '../models/video.dart';
import '../providers/app_provider.dart';
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
        'Summarized by YouTube InShorts';
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

    return Container(
      width: size.width,
      height: size.height,
      color: const Color(0xFF0F141C), // Deep dark background
      child: SafeArea(
        top: false,
        child: Column(
          children: [
            // ── Top Half: Thumbnail with Gradient Overlay & Action Badges ───────
            Expanded(
              flex: 5,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  // YouTube Thumbnail Image
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

                  // Dark Bottom Gradient
                  Positioned.fill(
                    child: Container(
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.black38,
                            Colors.transparent,
                            Color(0xFF0F141C),
                          ],
                          stops: [0.0, 0.5, 1.0],
                        ),
                      ),
                    ),
                  ),


                  // Channel Pill Badge & YouTube Link Button
                  Positioned(
                    top: MediaQuery.of(context).padding.top + 16,
                    left: 16,
                    right: 16,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // Channel Tag
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.7),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: Colors.white24, width: 0.8),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.play_circle_fill, size: 16, color: Color(0xFFFF0000)),
                              const SizedBox(width: 6),
                              Text(
                                video.channelName,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),

                        // Action Buttons: Bookmark & Share
                        Row(
                          children: [
                            // Bookmark Button
                            IconButton(
                              onPressed: () => provider.toggleBookmark(video),
                              icon: Icon(
                                video.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                                color: video.isBookmarked ? const Color(0xFFFF9500) : Colors.white,
                                size: 26,
                              ),
                            ),
                            // Share Button
                            IconButton(
                              onPressed: () => _shareSummary(context),
                              icon: const Icon(Icons.share_rounded, color: Colors.white, size: 24),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  // Direct Watch on YouTube FAB Floating over Thumbnail
                  Positioned(
                    bottom: 12,
                    right: 16,
                    child: FloatingActionButton.small(
                      heroTag: 'yt_${video.videoId}',
                      backgroundColor: const Color(0xFFFF0000),
                      onPressed: () => _openYouTubeUrl(video.videoId),
                      child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 24),
                    ),
                  ),
                ],
              ),
            ),

            // ── Bottom Half: Short InShorts Summary & Deep Digest Trigger ───────
            Expanded(
              flex: 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      video.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 19,
                        fontWeight: FontWeight.bold,
                        height: 1.25,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 12),

                    // InShorts Short Summary Paragraph (~100 words)
                    Expanded(
                      child: SingleChildScrollView(
                        physics: const BouncingScrollPhysics(),
                        child: Text(
                          video.shortSummary,
                          style: const TextStyle(
                            color: Color(0xFFD1D5DB), // Clean soft light text
                            fontSize: 15,
                            height: 1.5,
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 12),

                    // Bottom Action Bar: Listen TTS & Tap for Full Deep Digest
                    Row(
                      children: [
                        // Listen TTS Button
                        InkWell(
                          onTap: () => provider.speakShortSummary(video),
                          borderRadius: BorderRadius.circular(20),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            decoration: BoxDecoration(
                              color: isSpeaking ? const Color(0xFF2563EB) : const Color(0xFF1E293B),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: isSpeaking ? const Color(0xFF60A5FA) : Colors.white12,
                              ),
                            ),
                            child: Row(
                              children: [
                                Icon(
                                  isSpeaking ? Icons.volume_up_rounded : Icons.volume_mute_rounded,
                                  color: Colors.white,
                                  size: 18,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  isSpeaking ? 'Listening...' : 'Listen',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),

                        // Full Deep Digest Button (Primary Prompt)
                        Expanded(
                          child: ElevatedButton(
                            onPressed: () => _showFullSummaryModal(context),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF2563EB), // Deep Royal Blue
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(20),
                              ),
                              elevation: 2,
                            ),
                            child: const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  'Tap for Full Deep Digest',
                                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                                ),
                                SizedBox(width: 6),
                                Icon(Icons.arrow_upward_rounded, size: 18),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
