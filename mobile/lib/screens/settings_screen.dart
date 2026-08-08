import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/app_provider.dart';
import 'inshorts_feed_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TextEditingController _channelIdController = TextEditingController();
  final TextEditingController _channelNameController = TextEditingController();

  @override
  void initState() {
    super.initState();
    final provider = Provider.of<AppProvider>(context, listen: false);
    provider.fetchChannels();
  }

  @override
  void dispose() {
    _channelIdController.dispose();
    _channelNameController.dispose();
    super.dispose();
  }

  void _showAddChannelDialog(BuildContext context) {
    _channelIdController.clear();
    _channelNameController.clear();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E2634),
        title: const Text('Add YouTube Channel', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _channelNameController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Channel Name (e.g. Marques Brownlee)',
                labelStyle: TextStyle(color: Colors.white60),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _channelIdController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Channel Handle/URL/ID (e.g. @MKBHD or URL)',
                labelStyle: TextStyle(color: Colors.white60),
                enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () async {
              final name = _channelNameController.text.trim();
              final cid = _channelIdController.text.trim();
              if (name.isNotEmpty && cid.isNotEmpty) {
                final provider = Provider.of<AppProvider>(context, listen: false);
                final messenger = ScaffoldMessenger.of(context);
                
                // Close dialog immediately
                Navigator.pop(ctx);
                
                try {
                  await provider.addChannel(cid, name);
                  if (mounted) {
                    messenger.showSnackBar(
                      SnackBar(content: Text('Added channel "$name" and initiated sync!')),
                    );
                  }
                } catch (e) {
                  if (mounted) {
                    messenger.showSnackBar(
                      SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
                    );
                  }
                }
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF2563EB)),
            child: const Text('Add Channel', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showPrivacyPolicyDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E2634),
        title: const Text('Privacy Policy & Transparency', style: TextStyle(color: Colors.white)),
        content: const SingleChildScrollView(
          child: Text(
            'SkimTube respects user privacy:\n\n'
            '• No Personal Data Collection: SkimTube does not harvest personal user details, tracking tokens, or contacts.\n'
            '• Local Device Storage: Monitored channels, server configurations, and bookmarks are stored exclusively on your device via SharedPreferences.\n'
            '• Backend Communication: SkimTube connects securely to the SkimTube API backend service for retrieving video digests and RSS sync updates.\n'
            '• Third-Party Services: Public YouTube RSS feeds and transcripts are fetched securely via backend service without third-party ad profiling.\n',
            style: TextStyle(color: Colors.white70, fontSize: 13, height: 1.4),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close', style: TextStyle(color: Color(0xFF60A5FA))),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<AppProvider>(context);

    return Scaffold(
      backgroundColor: const Color(0xFF0F141C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141923),
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Image.asset(
                'assets/logo.png',
                width: 26,
                height: 26,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 10),
            const Text('Settings', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ],
        ),
        elevation: 0,
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [

              // ── Section 4: Bookmarks Shortcut & Privacy Policy ────────────────
              Material(
                color: const Color(0xFF181F2B),
                clipBehavior: Clip.antiAlias,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: const BorderSide(color: Colors.white12),
                ),
                child: Column(
                  children: [
                    ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
                      leading: const Icon(Icons.bookmark_rounded, color: Color(0xFFFF9500), size: 24),
                      title: const Text('Saved Bookmarks', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                      subtitle: const Text('Quick access to your bookmarked digests', style: TextStyle(color: Colors.white54, fontSize: 11.5)),
                      trailing: const Icon(Icons.arrow_forward_ios_rounded, color: Colors.white24, size: 14),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const InShortsFeedScreen(isBookmarksPage: true),
                          ),
                        );
                      },
                    ),
                    const Divider(height: 1, color: Colors.white10),
                    ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
                      leading: const Icon(Icons.privacy_tip_rounded, color: Color(0xFF10B981), size: 24),
                      title: const Text('Privacy Policy & Transparency', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                      subtitle: const Text('View data safety & storage details', style: TextStyle(color: Colors.white54, fontSize: 11.5)),
                      trailing: const Icon(Icons.info_outline_rounded, color: Colors.white24, size: 18),
                      onTap: () => _showPrivacyPolicyDialog(context),
                    ),
                  ],
                ),
              ),



              // ── Section 2: Channel Management ────────────────────────────────
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Monitored Channels',
                    style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  IconButton(
                    onPressed: () => _showAddChannelDialog(context),
                    icon: const Icon(Icons.add_circle_rounded, color: Color(0xFF60A5FA), size: 28),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              if (provider.channels.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 20),
                  child: Text(
                    'No channels added yet. Tap "+" to add a YouTube channel.',
                    style: TextStyle(color: Colors.white54, fontSize: 14),
                  ),
                )
              else
                ...provider.channels.map((channel) => Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF181F2B),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.white10),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.play_circle_fill, color: Color(0xFFFF0000), size: 24),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  channel.name,
                                  style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                                Text(
                                  channel.channelId,
                                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete_outline_rounded, color: Colors.redAccent),
                            onPressed: () => provider.deleteChannel(channel.channelId),
                          ),
                        ],
                      ),
                    )),

              const SizedBox(height: 24),

              // ── Section 3: Manual Sync Trigger ───────────────────────────────
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: (provider.isSyncing || provider.channels.isEmpty) ? null : () => provider.triggerSync(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981), // Emerald Green
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  icon: provider.isSyncing
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Icon(Icons.sync_rounded),
                  label: Text(
                    provider.isSyncing ? 'Syncing Feeds...' : 'Sync Feeds & Summarize Now',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
