class VideoModel {
  final int id;
  final String videoId;
  final String channelId;
  final String channelName;
  final String title;
  final String publishedAt;
  final String thumbnailUrl;
  final String shortSummary;
  final String contentType;
  bool isBookmarked;
  final String? labelApi;
  final String? labelLocal;
  final String? summaryApi;
  final String? summaryLocal;
  final String? summaryFile;

  VideoModel({
    required this.id,
    required this.videoId,
    required this.channelId,
    required this.channelName,
    required this.title,
    required this.publishedAt,
    required this.thumbnailUrl,
    required this.shortSummary,
    required this.contentType,
    this.isBookmarked = false,
    this.labelApi,
    this.labelLocal,
    this.summaryApi,
    this.summaryLocal,
    this.summaryFile,
  });

  factory VideoModel.fromJson(Map<String, dynamic> json) {
    return VideoModel(
      id: json['id'] ?? 0,
      videoId: json['video_id'] ?? '',
      channelId: json['channel_id'] ?? '',
      channelName: json['channel_name'] ?? 'YouTube Channel',
      title: json['title'] ?? '',
      publishedAt: json['published_at'] ?? '',
      thumbnailUrl: json['thumbnail_url'] ?? '',
      shortSummary: json['short_summary'] ?? '',
      contentType: json['content_type'] ?? 'general',
      isBookmarked: json['is_bookmarked'] ?? false,
      labelApi: json['label_api'],
      labelLocal: json['label_local'],
      summaryApi: json['summary_api'],
      summaryLocal: json['summary_local'],
      summaryFile: json['summary_file'],
    );
  }
}
