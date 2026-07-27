import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../widgets/inshorts_card.dart';


class InShortsFeedScreen extends StatefulWidget {
  const InShortsFeedScreen({Key? key}) : super(key: key);

  @override
  State<InShortsFeedScreen> createState() => _InShortsFeedScreenState();
}

class _InShortsFeedScreenState extends State<InShortsFeedScreen> {
  final PageController _pageController = PageController();

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AppProvider>(context);

    return Scaffold(
      backgroundColor: const Color(0xFF0F141C),
      body: Stack(
        children: [
          // ── Main PageView: Vertical Snapping InShorts Feed Cards ───────────
          if (provider.isLoading)
            const Center(
              child: CircularProgressIndicator(color: Color(0xFF2563EB)),
            )
          else if (provider.videos.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.slideshow_rounded, size: 64, color: Colors.white24),
                    const SizedBox(height: 16),
                    const Text(
                      'No Summaries Available',
                      style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Add channel IDs in Settings or tap "Sync" to generate your daily byte-sized video digests.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white60, fontSize: 14, height: 1.5),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: () => provider.refreshFeed(),
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2563EB)),
                      icon: const Icon(Icons.refresh_rounded, color: Colors.white),
                      label: const Text('Refresh Feed', style: TextStyle(color: Colors.white)),
                    ),
                  ],
                ),
              ),
            )
          else
            PageView.builder(
              controller: _pageController,
              scrollDirection: Axis.vertical,
              itemCount: provider.videos.length,
              itemBuilder: (context, index) {
                return InShortsCard(video: provider.videos[index]);
              },
            ),



          // ── Offline Connection Banner (if backend is offline) ────────────
          if (!provider.isOnline)
            Positioned(
              top: MediaQuery.of(context).padding.top + 56,
              left: 16,
              right: 16,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFFDC2626).withOpacity(0.9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.wifi_off_rounded, color: Colors.white, size: 16),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Backend Server Offline — Check settings or start FastAPI',
                        style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
