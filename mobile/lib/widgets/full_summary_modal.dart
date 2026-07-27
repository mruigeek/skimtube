import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
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

class _FullSummaryModalState extends State<FullSummaryModal> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  VideoModel? _fullVideo;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
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

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final video = _fullVideo ?? widget.fallbackVideo;
    final summaryApi = video.summaryApi ?? '*Digest not available via TranscriptAPI.*';
    final summaryLocal = video.summaryLocal ?? '*Digest not available via local fallback.*';

    return Container(
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
                        video.channelName,
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

          // Version A / Version B Tab Bar
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 20),
            height: 42,
            decoration: BoxDecoration(
              color: const Color(0xFF1E2634),
              borderRadius: BorderRadius.circular(21),
            ),
            child: TabBar(
              controller: _tabController,
              indicator: BoxDecoration(
                color: const Color(0xFF2563EB),
                borderRadius: BorderRadius.circular(21),
              ),
              labelColor: Colors.white,
              unselectedLabelColor: Colors.white60,
              labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
              tabs: const [
                Tab(text: '🔵 Version A (API)'),
                Tab(text: '🟢 Version B (Local)'),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Tab Views with Full Markdown Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF2563EB)))
                : TabBarView(
                    controller: _tabController,
                    children: [
                      _buildMarkdownView(summaryApi),
                      _buildMarkdownView(summaryLocal),
                    ],
                  ),
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
    );
  }

  Widget _buildMarkdownView(String markdownContent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Markdown(
        data: markdownContent,
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
