import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../widgets/inshorts_card.dart';
import 'settings_screen.dart';

class InShortsFeedScreen extends StatefulWidget {
  const InShortsFeedScreen({Key? key}) : super(key: key);

  @override
  State<InShortsFeedScreen> createState() => _InShortsFeedScreenState();
}

class _InShortsFeedScreenState extends State<InShortsFeedScreen> {
  final PageController _pageController = PageController();

  final List<String> _categories = ['All', 'Tech', 'News', 'General'];

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

          // ── Floating Header Overlay: App Name & Settings Action ────────────
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 16,
            right: 16,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Logo & App Name
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF0000),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 18),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      'YouTube InShorts',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                      ),
                    ),
                  ],
                ),

                // Right Actions: Bookmark Toggle & Settings
                Row(
                  children: [
                    // Bookmarks Filter Toggle
                    IconButton(
                      icon: Icon(
                        provider.showBookmarkedOnly ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                        color: provider.showBookmarkedOnly ? const Color(0xFFFF9500) : Colors.white,
                        size: 24,
                      ),
                      onPressed: () => provider.toggleBookmarkedOnly(),
                    ),
                    // Settings Button
                    IconButton(
                      icon: const Icon(Icons.settings_rounded, color: Colors.white, size: 24),
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

          // ── Category Pills Floating Filter Bar (Below Header) ─────────────
          Positioned(
            top: MediaQuery.of(context).padding.top + 56,
            left: 0,
            right: 0,
            child: SizedBox(
              height: 36,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _categories.length,
                itemBuilder: (context, index) {
                  final cat = _categories[index];
                  final isSelected = provider.selectedCategory == cat;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(cat),
                      selected: isSelected,
                      selectedColor: const Color(0xFF2563EB),
                      backgroundColor: Colors.black.withOpacity(0.6),
                      labelStyle: TextStyle(
                        color: isSelected ? Colors.white : Colors.white70,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        fontSize: 12,
                      ),
                      onSelected: (selected) {
                        if (selected) {
                          provider.setCategory(cat);
                        }
                      },
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
