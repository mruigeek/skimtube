import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import '../widgets/inshorts_card.dart';
import '../widgets/welcome_card.dart';
import 'settings_screen.dart';

class InShortsFeedScreen extends StatefulWidget {
  final bool isBookmarksPage;

  const InShortsFeedScreen({Key? key, this.isBookmarksPage = false}) : super(key: key);

  @override
  State<InShortsFeedScreen> createState() => _InShortsFeedScreenState();
}

class _InShortsFeedScreenState extends State<InShortsFeedScreen> {
  final PageController _pageController = PageController();

  @override
  void initState() {
    super.initState();
    if (widget.isBookmarksPage) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          Provider.of<AppProvider>(context, listen: false).setBookmarkedOnly(true);
        }
      });
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Widget _buildEmptyBookmarksState(BuildContext context, AppProvider provider) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFF9500).withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.bookmark_border_rounded,
              size: 64,
              color: Color(0xFFFF9500),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'No Bookmarks Yet',
            style: TextStyle(
              color: Color(0xFF111827),
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Keep track of key video summaries by tapping the bookmark icon on feed cards. They will appear here for quick access.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF4B5563),
              fontSize: 14.5,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 32),
          ElevatedButton.icon(
            onPressed: () {
              if (widget.isBookmarksPage) {
                Navigator.pop(context);
              } else {
                provider.toggleBookmarkedOnly();
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2563EB),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            icon: const Icon(Icons.feed_rounded, size: 18),
            label: const Text('Back to Main Feed', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AppProvider>(context);

    return PopScope(
      canPop: true,
      onPopInvoked: (didPop) {
        if (didPop && widget.isBookmarksPage) {
          provider.setBookmarkedOnly(false);
        }
      },
      child: Scaffold(
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
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: provider.showBookmarkedOnly
                      ? _buildEmptyBookmarksState(context, provider)
                      : const WelcomeCard(),
                ),
              )
            else
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: PageView.builder(
                    controller: _pageController,
                    scrollDirection: Axis.vertical,
                    itemCount: provider.videos.length,
                    onPageChanged: (index) {
                      provider.stopTts();
                    },
                    itemBuilder: (context, index) {
                      return InShortsCard(video: provider.videos[index]);
                    },
                  ),
                ),
              ),
  
            // ── Top Header Overlay (SkimTube Brand + Bookmark Filter Toggle) ───
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                height: MediaQuery.of(context).padding.top + 56,
                padding: EdgeInsets.fromLTRB(18, MediaQuery.of(context).padding.top, 18, 0),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.black.withOpacity(0.75),
                      Colors.black.withOpacity(0.3),
                      Colors.transparent,
                    ],
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Logo/Title
                    Row(
                      children: [
                        if (provider.showBookmarkedOnly) ...[
                          GestureDetector(
                            onTap: () {
                              if (widget.isBookmarksPage) {
                                Navigator.pop(context);
                              } else {
                                provider.toggleBookmarkedOnly();
                              }
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              decoration: BoxDecoration(
                                color: const Color(0xFF1E293B), // High-contrast solid dark background
                                borderRadius: BorderRadius.circular(18),
                                border: Border.all(color: const Color(0xFFFF9500), width: 1.5),
                              ),
                              child: const Row(
                                children: [
                                  Icon(Icons.arrow_back_rounded, color: Colors.white, size: 14),
                                  SizedBox(width: 6),
                                  Text(
                                    'Bookmarked Feeds',
                                    style: TextStyle(
                                      color: Colors.white, // White text for high visibility
                                      fontSize: 12,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
  
                    // Actions
                    Row(
                      children: [
                        if (provider.isSyncing)
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 12),
                            child: SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.2,
                                color: Colors.white70,
                              ),
                            ),
                          )
                        else if (!widget.isBookmarksPage && provider.channels.isNotEmpty)
                          IconButton(
                            tooltip: 'Sync Feed',
                            icon: const Icon(Icons.sync_rounded, color: Colors.white70, size: 22),
                            onPressed: () => provider.triggerSync(),
                          ),
                        if (!widget.isBookmarksPage)
                          IconButton(
                            tooltip: provider.showBookmarkedOnly ? 'Show all summaries' : 'Show bookmarked only',
                            icon: Icon(
                              provider.showBookmarkedOnly
                                  ? Icons.bookmark_rounded
                                  : Icons.bookmark_border_rounded,
                              color: provider.showBookmarkedOnly ? const Color(0xFFFF9500) : Colors.white70,
                              size: 22,
                            ),
                            onPressed: () => provider.toggleBookmarkedOnly(),
                          ),
                      ],
                    ),
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
