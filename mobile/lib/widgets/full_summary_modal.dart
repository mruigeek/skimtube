import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';
import '../models/video.dart';
import '../providers/app_provider.dart';

class FullSummaryModal extends StatefulWidget {
  final String videoId;
  final VideoModel fallbackVideo;

  const FullSummaryModal({
    Key? key,
    required this.videoId,
    required this.fallbackVideo,
  }) : super(key: key);

  @override
  State<FullSummaryModal> createState() => _FullSummaryModalState();
}

class _FullSummaryModalState extends State<FullSummaryModal> {
  VideoModel? _fullVideo;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadFullDetail();
  }

  Future<void> _loadFullDetail() async {
    final provider = Provider.of<AppProvider>(context, listen: false);
    try {
      final detail = await provider.fetchFullVideoDetail(widget.videoId);
      if (mounted) {
        setState(() {
          _fullVideo = detail;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _fullVideo = widget.fallbackVideo;
          _isLoading = false;
        });
      }
    }
  }

  void _openYouTubeUrl() async {
    final uri = Uri.parse('https://www.youtube.com/watch?v=${widget.videoId}');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  String _formatPublishedAt(String publishedAtStr) {
    try {
      final DateTime dt = DateTime.parse(publishedAtStr);
      return DateFormat('dd MMM yyyy hh:mm a').format(dt);
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final video = _fullVideo ?? widget.fallbackVideo;
    final String summaryContent = (video.summaryApi != null && video.summaryApi!.isNotEmpty)
        ? video.summaryApi!
        : (video.summaryLocal != null && video.summaryLocal!.isNotEmpty)
            ? video.summaryLocal!
            : video.shortSummary;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Container(
          height: MediaQuery.of(context).size.height * 0.88,
          decoration: const BoxDecoration(
            color: Color(0xFF141923),
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            children: [
              // Drag Handle
              const SizedBox(height: 12),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white30,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 12),

              // Modal Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            video.publishedAt.isNotEmpty
                                ? '${video.channelName.toUpperCase()} • ${_formatPublishedAt(video.publishedAt)}'
                                : video.channelName.toUpperCase(),
                            style: const TextStyle(
                              color: Color(0xFFFF3B30),
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            video.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 17,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded, color: Colors.white70),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Single Full Summary Markdown Content View
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator(color: Color(0xFF2563EB)))
                    : _buildMarkdownView(summaryContent),
              ),

              // Bottom Action Bar: Open on YouTube
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  color: Color(0xFF1E2634),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
                ),
                child: SafeArea(
                  top: false,
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _openYouTubeUrl,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFFF0000),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      icon: const Icon(Icons.play_arrow_rounded, size: 22),
                      label: const Text(
                        'Watch Video on YouTube',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _cleanMarkdownContent(String raw) {
    // 1. Remove TL;DR header and its content block up to ## Key Takeaways
    String clean = raw.replaceAll(
      RegExp(r'##\s*TL;?DR[\s\S]*?(?=##\s*Key Takeaways|##\s*Detailed Breakdown|$)', caseSensitive: false),
      '',
    );

    // 2. Clean out meta-attribution phrases & opening filler phrases
    clean = clean.replaceAll(
      RegExp(
        r'\b(The speaker begins by stating that|The speaker begins by stating|The speaker begins by|The speaker states that|The speaker states|The speaker opens with|The speaker mentions that|The speaker mentions|The speaker explains that|The speaker explains|The speaker discusses|The speaker suggests|The speaker advises|The speaker highlights|The presenter begins by stating|The presenter begins by|The presenter recommends|The presenter suggests|The presenter advises|The video begins by stating|The video begins by|The video starts by stating|The video starts by|The video starts with|The video discusses|The video covers|The author explains|In this video|According to the speaker)\b\s*',
        caseSensitive: false,
      ),
      '',
    );

    // 3. Clean any leftover standalone "that " at sentence or bullet starts
    clean = clean.replaceAll(RegExp(r'(^|\n|-\s+)\s*that\s+', caseSensitive: false), r'\1');

    // 4. Ensure capital first letter after bullet points
    clean = clean.replaceAllMapped(
      RegExp(r'(-\s+)([a-z])'),
      (match) => '${match.group(1)}${match.group(2)!.toUpperCase()}',
    );

    return clean.trim();
  }

  Widget _buildMarkdownView(String markdownContent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Markdown(
        data: _cleanMarkdownContent(markdownContent),
        physics: const BouncingScrollPhysics(),
        styleSheet: MarkdownStyleSheet(
          h1: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          h2: const TextStyle(color: Color(0xFF60A5FA), fontSize: 17, fontWeight: FontWeight.bold, height: 1.8),
          h3: const TextStyle(color: Colors.white70, fontSize: 15, fontWeight: FontWeight.bold),
          p: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 14, height: 1.6),
          listBullet: const TextStyle(color: Color(0xFF60A5FA), fontSize: 16),
          blockquote: const TextStyle(color: Color(0xFF94A3B8), fontStyle: FontStyle.italic),
          blockquoteDecoration: BoxDecoration(
            color: const Color(0xFF1E293B),
            borderRadius: BorderRadius.circular(8),
            border: const Border(left: BorderSide(color: Color(0xFF2563EB), width: 4)),
          ),
        ),
      ),
    );
  }
}
