/**
 * CareerSync — Resume-Based Career and Resource Recommendation System
 * Frontend Application Script (script.js)
 * 
 * Features:
 * - UI-level PDF & DOCX file selection and validation (drag-and-drop + browse)
 * - Clear and remove selected file functionality
 * - Job description character counter
 * - Sidebar navigation and scroll-spy active state handling
 * - Mobile navigation menu toggle
 * - Strict adherence: NO fake analysis scores or fabricated results
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------------------
  // 1. Element References
  // -------------------------------------------------------------------------
  const dropZone = document.getElementById('dropZone');
  const resumeFileInput = document.getElementById('resumeFileInput');
  const selectedFileInfo = document.getElementById('selectedFileInfo');
  const fileNameDisplay = document.getElementById('fileName');
  const fileSizeDisplay = document.getElementById('fileSize');
  const fileFormatIcon = document.getElementById('fileFormatIcon');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const fileUploadError = document.getElementById('fileUploadError');
  const fileUploadErrorMessage = document.getElementById('fileUploadErrorMessage');

  const targetJobTitleInput = document.getElementById('targetJobTitle');
  const jobDescriptionInput = document.getElementById('jobDescriptionInput');
  const jobDescCharCount = document.getElementById('jobDescCharCount');
  const clearInputsBtn = document.getElementById('clearInputsBtn');
  const deleteResumeBtn = document.getElementById('deleteResumeBtn');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const analysisStatusMessage = document.getElementById('analysisStatusMessage');
  const statusMessageIcon = document.getElementById('statusMessageIcon');
  const statusMessageText = document.getElementById('statusMessageText');

  // Extracted Profile Card Elements (Stage 4.3 Integration)
  const extractedProfileCard = document.getElementById('extractedProfileCard');
  const profileCandidateName = document.getElementById('profileCandidateName');
  const profileCandidateEmail = document.getElementById('profileCandidateEmail');
  const profileCandidatePhone = document.getElementById('profileCandidatePhone');
  const profileSkillCount = document.getElementById('profileSkillCount');
  const extractedSkillsList = document.getElementById('extractedSkillsList');
  const unmatchedSkillsSection = document.getElementById('unmatchedSkillsSection');
  const unmatchedSkillsList = document.getElementById('unmatchedSkillsList');
  const extractedEducationList = document.getElementById('extractedEducationList');
  const extractedProjectsList = document.getElementById('extractedProjectsList');
  const extractedExperienceList = document.getElementById('extractedExperienceList');

  // API Base URL (FastAPI Backend Server)
  // Resolution order:
  // 1. <meta name="careersync-api-url" content="..."> (decoupled Vercel/CDN deployment)
  // 2. window.__CAREERSYNC_CONFIG__.API_BASE_URL (runtime injection)
  // 3. window.CAREERSYNC_API_URL (global variable)
  // 4. http://127.0.0.1:8000 (local development via Live Server port 5500 or file://)
  // 5. Empty string '' (same-origin relative requests for unified deployment on Render/FastAPI)
  const metaApiUrl = document.querySelector('meta[name="careersync-api-url"]')?.getAttribute('content');
  const rawApiBaseUrl = (metaApiUrl && metaApiUrl.trim())
    || (window.__CAREERSYNC_CONFIG__ && window.__CAREERSYNC_CONFIG__.API_BASE_URL)
    || (typeof window.CAREERSYNC_API_URL === 'string' && window.CAREERSYNC_API_URL.trim())
    || (window.location.port === '5500' || window.location.protocol === 'file:'
        ? 'http://127.0.0.1:8000'
        : '');
  const API_BASE_URL = rawApiBaseUrl ? rawApiBaseUrl.replace(/\/+$/, '') : '';

  // Overview status displays
  const overviewResumeStatus = document.getElementById('overviewResumeStatus');
  const overviewRoleStatus = document.getElementById('overviewRoleStatus');
  const overviewScoreStatus = document.getElementById('overviewScoreStatus');
  const overviewScoreHint = document.getElementById('overviewScoreHint');
  const overviewGapStatus = document.getElementById('overviewGapStatus');

  // View Containers & Settings Elements
  const dashboardView = document.getElementById('dashboardView');
  const settingsView = document.getElementById('settingsView');
  const settingsNavLink = document.getElementById('settingsNavLink');
  const topBarTitle = document.getElementById('topBarTitle');
  const topBarSubtitle = document.getElementById('topBarSubtitle');
  const themeLightBtn = document.getElementById('themeLightBtn');
  const themeDarkBtn = document.getElementById('themeDarkBtn');

  // Navigation elements
  const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');
  const sections = document.querySelectorAll('.dashboard-section');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const sidebar = document.getElementById('sidebar');

  // Job Matching DOM References
  const jobMatchingEmptyCard = document.getElementById('jobMatchingEmptyCard');
  const jobMatchingLoadingCard = document.getElementById('jobMatchingLoadingCard');
  const jobMatchingErrorCard = document.getElementById('jobMatchingErrorCard');
  const jobMatchingErrorMessage = document.getElementById('jobMatchingErrorMessage');
  const jobMatchingRetryBtn = document.getElementById('jobMatchingRetryBtn');
  const jobMatchingResultsCard = document.getElementById('jobMatchingResultsCard');
  const jobMatchingRankBadge = document.getElementById('jobMatchingRankBadge');
  const jobRoleSelectorList = document.getElementById('jobRoleSelectorList');
  const matchRoleTitle = document.getElementById('matchRoleTitle');
  const matchRoleDomain = document.getElementById('matchRoleDomain');
  const matchScoreValue = document.getElementById('matchScoreValue');
  const matchRequiredCoverage = document.getElementById('matchRequiredCoverage');
  const matchExplanationText = document.getElementById('matchExplanationText');
  const matchedSkillsCountBadge = document.getElementById('matchedSkillsCountBadge');
  const matchedSkillsChipsList = document.getElementById('matchedSkillsChipsList');
  const missingRequiredCountBadge = document.getElementById('missingRequiredCountBadge');
  const missingRequiredChipsList = document.getElementById('missingRequiredChipsList');
  const missingPreferredCountBadge = document.getElementById('missingPreferredCountBadge');
  const missingPreferredChipsList = document.getElementById('missingPreferredChipsList');
  const matchFormulaText = document.getElementById('matchFormulaText');
  const matchMatchedWeight = document.getElementById('matchMatchedWeight');
  const matchTotalWeight = document.getElementById('matchTotalWeight');
  const matchRequiredWeightRatio = document.getElementById('matchRequiredWeightRatio');

  // Skill Gap Analysis DOM References
  const skillGapEmptyCard = document.getElementById('skillGapEmptyCard');
  const skillGapLoadingCard = document.getElementById('skillGapLoadingCard');
  const skillGapErrorCard = document.getElementById('skillGapErrorCard');
  const skillGapErrorMessage = document.getElementById('skillGapErrorMessage');
  const skillGapRetryBtn = document.getElementById('skillGapRetryBtn');
  const skillGapResultsCard = document.getElementById('skillGapResultsCard');
  const skillGapHeaderTitle = document.getElementById('skillGapHeaderTitle');
  const skillGapRankBadge = document.getElementById('skillGapRankBadge');
  const skillGapRoleSelectorList = document.getElementById('skillGapRoleSelectorList');
  const gapRoleTitle = document.getElementById('gapRoleTitle');
  const gapRoleDomain = document.getElementById('gapRoleDomain');
  const gapScoreValue = document.getElementById('gapScoreValue');
  const gapTechScoreValue = document.getElementById('gapTechScoreValue');
  const gapPossessedCount = document.getElementById('gapPossessedCount');
  const gapTotalMissingCount = document.getElementById('gapTotalMissingCount');
  const gapExplanationText = document.getElementById('gapExplanationText');
  const gapCriticalCountBadge = document.getElementById('gapCriticalCountBadge');
  const gapCriticalSkillsList = document.getElementById('gapCriticalSkillsList');
  const gapSecondaryCountBadge = document.getElementById('gapSecondaryCountBadge');
  const gapSecondarySkillsList = document.getElementById('gapSecondarySkillsList');
  const gapPossessedCountBadge = document.getElementById('gapPossessedCountBadge');
  const gapPossessedChipsList = document.getElementById('gapPossessedChipsList');
  const overviewGapHint = document.getElementById('overviewGapHint');

  // Career Recommendations DOM References
  const careerRecEmptyCard = document.getElementById('careerRecEmptyCard');
  const careerRecLoadingCard = document.getElementById('careerRecLoadingCard');
  const careerRecErrorCard = document.getElementById('careerRecErrorCard');
  const careerRecErrorMessage = document.getElementById('careerRecErrorMessage');
  const careerRecRetryBtn = document.getElementById('careerRecRetryBtn');
  const careerRecResultsCard = document.getElementById('careerRecResultsCard');
  const careerRecHeaderTitle = document.getElementById('careerRecHeaderTitle');
  const careerRecTopBadge = document.getElementById('careerRecTopBadge');
  const careerRecRoleSelectorList = document.getElementById('careerRecRoleSelectorList');
  const recRoleTitle = document.getElementById('recRoleTitle');
  const recRoleDomain = document.getElementById('recRoleDomain');
  const recMatchScoreValue = document.getElementById('recMatchScoreValue');
  const recTechScoreValue = document.getElementById('recTechScoreValue');
  const recFitLevelBadge = document.getElementById('recFitLevelBadge');
  const recRankValue = document.getElementById('recRankValue');
  const recRationaleText = document.getElementById('recRationaleText');
  const recMatchedSkillsCountBadge = document.getElementById('recMatchedSkillsCountBadge');
  const recMatchedChipsList = document.getElementById('recMatchedChipsList');
  const recCriticalMissingCountBadge = document.getElementById('recCriticalMissingCountBadge');
  const recCriticalChipsList = document.getElementById('recCriticalChipsList');
  const recSecondaryMissingCountBadge = document.getElementById('recSecondaryMissingCountBadge');
  const recSecondaryChipsList = document.getElementById('recSecondaryChipsList');

  // Resource & Certification Recommendations DOM references
  const resourceRecEmptyCard = document.getElementById('resourceRecEmptyCard');
  const resourceRecLoadingCard = document.getElementById('resourceRecLoadingCard');
  const resourceRecErrorCard = document.getElementById('resourceRecErrorCard');
  const resourceRecErrorMessage = document.getElementById('resourceRecErrorMessage');
  const resourceRecRetryBtn = document.getElementById('resourceRecRetryBtn');
  const resourceRecResultsCard = document.getElementById('resourceRecResultsCard');
  const resourceRecHeaderBadge = document.getElementById('resourceRecHeaderBadge');
  const resourceRecRoleSelectorList = document.getElementById('resourceRecRoleSelectorList');
  const resRoleTitle = document.getElementById('resRoleTitle');
  const resMatchScoreValue = document.getElementById('resMatchScoreValue');
  const resTotalResourcesCount = document.getElementById('resTotalResourcesCount');
  const resTotalCertificationsCount = document.getElementById('resTotalCertificationsCount');
  const resourceRecFilterTabs = document.getElementById('resourceRecFilterTabs');
  const resourceRecFilterAllBtn = document.getElementById('resourceRecFilterAllBtn');
  const resourceRecFilterResourcesBtn = document.getElementById('resourceRecFilterResourcesBtn');
  const resourceRecFilterCertificationsBtn = document.getElementById('resourceRecFilterCertificationsBtn');
  const resourceRecLearningSection = document.getElementById('resourceRecLearningSection');
  const resourceRecLearningCountBadge = document.getElementById('resourceRecLearningCountBadge');
  const resourceRecLearningList = document.getElementById('resourceRecLearningList');
  const resourceRecCertSection = document.getElementById('resourceRecCertSection');
  const resourceRecCertCountBadge = document.getElementById('resourceRecCertCountBadge');
  const resourceRecCertList = document.getElementById('resourceRecCertList');

  // State
  let currentFile = null;
  let currentResumeId = null;
  let currentResumeToken = null;
  let currentView = 'dashboard';
  const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5MB
  const ALLOWED_EXTENSIONS = ['.pdf', '.docx'];
  const THEME_STORAGE_KEY = 'careerSync_theme';

  /**
   * Helper to construct HTTP request headers for resume-specific API calls.
   * Attaches the temporary access token kept in JavaScript memory.
   */
  function getAuthHeaders(extraHeaders = {}) {
    const headers = { 'Accept': 'application/json', ...extraHeaders };
    if (currentResumeToken) {
      headers['X-Resume-Token'] = currentResumeToken;
    }
    return headers;
  }

  // Job Matching State
  let currentMatchingRequestId = 0;
  let currentMatchingData = null;
  let selectedJobRoleId = null;

  // Skill Gap Analysis State
  let currentSkillGapRequestId = 0;
  let currentSkillGapData = null;
  let selectedSkillGapRoleId = null;
  let isSkillGapAnalyzing = false;

  // Career Recommendations State
  let currentCareerRecRequestId = 0;
  let currentCareerRecData = null;
  let selectedCareerRecRoleId = null;
  let isCareerRecAnalyzing = false;

  // Learning Resources & Certifications State
  let currentResourceRecRequestId = 0;
  let currentResourceRecData = null;
  let selectedResourceRecRoleId = null;
  let selectedResourceRecFilter = 'all'; // 'all', 'resources', 'certifications'
  let isResourceRecAnalyzing = false;

  // Unified Shared Selected Career Role State across All Sections
  let currentSelectedRoleId = null;
  let isSyncingRoleSelection = false;
  let previousTargetRoleId = null;

  // Independent Expandable State for Role Selection Lists (More / Less)
  let isExpandedJobMatching = false;
  let isExpandedSkillGap = false;
  let isExpandedCareerRec = false;
  let isExpandedResourceRec = false;

  /**
   * Helper to format and clean role titles by removing legacy prefixes
   */
  function formatJobRoleTitle(title) {
    if (!title || typeof title !== 'string') return '';
    return title.replace(/^(?:Junior|Associate|Entry-Level)\s+/i, '').trim();
  }

  /**
   * Helper to determine active target role match object from user input and catalog matches.
   * Returns null if no target role is specified or if typed title is not in catalog.
   */
  function getTargetRoleMatch() {
    const userTarget = targetJobTitleInput ? targetJobTitleInput.value.trim() : '';
    if (!userTarget) return null;
    if (!currentMatchingData || !Array.isArray(currentMatchingData.matches) || currentMatchingData.matches.length === 0) {
      return null;
    }
    return findTargetRoleMatch(userTarget, currentMatchingData.matches);
  }

  /**
   * Helper to construct the ordered list of roles for any section:
   * 1. Target role first (pinned), if valid target role is present.
   * 2. Alternatives ranked by actual compatibility score descending (excluding target role).
   * 3. If collapsed: Top 5 alternatives (total up to 6 roles with target, or 5 if no target).
   *    Plus, if the globally selected role is an alternative outside the top 5, include it immediately after top 5.
   * 4. If expanded: all 18 roles (target first, then all 17 alternatives by score).
   */
  function buildSectionRoleDisplayList(rawItems, isExpanded, targetRoleId, selectedRoleId) {
    if (!Array.isArray(rawItems) || rawItems.length === 0) return [];

    // Map compatibility score from matches for consistent cross-section ranking
    const scoreMap = new Map();
    if (currentMatchingData && Array.isArray(currentMatchingData.matches)) {
      currentMatchingData.matches.forEach(m => scoreMap.set(m.job_role_id, m.match_score));
    }

    const getScore = (item) => {
      if (scoreMap.has(item.job_role_id)) return scoreMap.get(item.job_role_id);
      if (item.match_score !== undefined) return item.match_score;
      if (item.match_percentage !== undefined) return item.match_percentage;
      if (item.compatibility_score !== undefined) return item.compatibility_score;
      return 0;
    };

    let targetItem = null;
    const alternatives = [];

    rawItems.forEach(item => {
      if (targetRoleId && item.job_role_id === targetRoleId) {
        targetItem = item;
      } else {
        alternatives.push(item);
      }
    });

    // Rank alternatives by compatibility score descending
    alternatives.sort((a, b) => getScore(b) - getScore(a));

    if (isExpanded) {
      return targetItem ? [targetItem, ...alternatives] : alternatives;
    }

    // Collapsed: Target role (if any) + Top 5 alternatives
    const top5Alternatives = alternatives.slice(0, 5);
    const result = targetItem ? [targetItem, ...top5Alternatives] : top5Alternatives;

    // If currently selected role is an alternative outside the top 5, keep it visible immediately after top 5
    if (selectedRoleId) {
      const isAlreadyDisplayed = result.some(item => item.job_role_id === selectedRoleId);
      if (!isAlreadyDisplayed) {
        const selectedItem = rawItems.find(item => item.job_role_id === selectedRoleId);
        if (selectedItem) {
          result.push(selectedItem);
        }
      }
    }

    return result;
  }

  /**
   * Synchronize selected career role across all relevant sections:
   * - Job Matching
   * - Skill Gap Analysis
   * - Career Recommendations
   * - Learning Resources & Certifications
   *
   * Operates purely in-memory on loaded data without page reload, scrolling, or duplicate API requests.
   */
  function selectCareerRole(jobRoleId, options = {}) {
    const roleId = parseInt(jobRoleId, 10);
    if (isNaN(roleId) || roleId <= 0) return;
    if (isSyncingRoleSelection) return;

    // Automatically collapse the section where the user clicked if it was expanded
    if (options.source === 'job-matching') {
      isExpandedJobMatching = false;
    } else if (options.source === 'skill-gap') {
      isExpandedSkillGap = false;
    } else if (options.source === 'career-recommendations') {
      isExpandedCareerRec = false;
    } else if (options.source === 'learning-resources') {
      isExpandedResourceRec = false;
    }

    isSyncingRoleSelection = true;
    try {
      currentSelectedRoleId = roleId;
      selectedJobRoleId = roleId;
      selectedSkillGapRoleId = roleId;
      selectedCareerRecRoleId = roleId;
      selectedResourceRecRoleId = roleId;

      // 1. Synchronize Job Matching Section
      if (currentMatchingData && Array.isArray(currentMatchingData.matches) && currentMatchingData.matches.length > 0) {
        if (currentMatchingData.matches.some(m => m.job_role_id === roleId)) {
          renderJobMatchingButtons();
          renderSelectedRoleDetail(roleId);
        }
      }

      // 2. Synchronize Skill Gap Analysis Section
      if (currentSkillGapData && Array.isArray(currentSkillGapData.role_gaps) && currentSkillGapData.role_gaps.length > 0) {
        if (currentSkillGapData.role_gaps.some(r => r.job_role_id === roleId)) {
          renderSkillGapButtons();
          renderSelectedSkillGapDetail(roleId);
        }
      }

      // 3. Synchronize Career Recommendations Section
      if (currentCareerRecData && Array.isArray(currentCareerRecData.recommendations) && currentCareerRecData.recommendations.length > 0) {
        if (currentCareerRecData.recommendations.some(r => r.job_role_id === roleId)) {
          renderCareerRecButtons();
          renderSelectedCareerRecDetail(roleId);
        }
      }

      // 4. Synchronize Learning Resources & Certifications Section
      if (currentResourceRecData && Array.isArray(currentResourceRecData.roles) && currentResourceRecData.roles.length > 0) {
        if (currentResourceRecData.roles.some(r => r.job_role_id === roleId)) {
          renderResourceRecButtons();
          renderSelectedResourceRecDetail(roleId);
        }
      }
    } finally {
      isSyncingRoleSelection = false;
    }
  }

  /**
   * Helper to retrieve currently analyzed resume ID for subsequent integration stages
   */
  function getCurrentResumeId() {
    return currentResumeId;
  }

  // -------------------------------------------------------------------------
  // 1b. Appearance Theme Engine (Light / Dark Mode with Persistence)
  // -------------------------------------------------------------------------
  function applyTheme(theme) {
    const selectedTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', selectedTheme);

    try {
      localStorage.setItem(THEME_STORAGE_KEY, selectedTheme);
    } catch (e) {
      // Graceful fallback if localStorage is disabled or restricted
    }

    if (themeLightBtn && themeDarkBtn) {
      if (selectedTheme === 'dark') {
        themeDarkBtn.classList.add('active');
        themeLightBtn.classList.remove('active');
      } else {
        themeLightBtn.classList.add('active');
        themeDarkBtn.classList.remove('active');
      }
    }
  }

  // Restore saved theme on load (default to Light Mode if no preference)
  const savedTheme = (() => {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY) || 'light';
    } catch (e) {
      return 'light';
    }
  })();
  applyTheme(savedTheme);

  if (themeLightBtn) {
    themeLightBtn.addEventListener('click', () => applyTheme('light'));
  }
  if (themeDarkBtn) {
    themeDarkBtn.addEventListener('click', () => applyTheme('dark'));
  }

  // -------------------------------------------------------------------------
  // 2. File Upload & Validation (UI Level)
  // -------------------------------------------------------------------------

  /**
   * Format byte count into human-readable string
   */
  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  /**
   * Validate file extension and size
   */
  function validateFile(file) {
    const fileName = file.name.toLowerCase();
    const isExtensionValid = ALLOWED_EXTENSIONS.some(ext => fileName.endsWith(ext));

    if (!isExtensionValid) {
      return {
        valid: false,
        message: 'Unsupported format. Please select a valid PDF (.pdf) or Word document (.docx).'
      };
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return {
        valid: false,
        message: 'File size exceeds the 5MB limit. Please upload a smaller file.'
      };
    }

    if (file.size === 0) {
      return {
        valid: false,
        message: 'The selected file appears to be empty (0 bytes).'
      };
    }

    return { valid: true };
  }

  /**
   * Display file selection details in the UI
   */
  function handleSelectedFile(file) {
    hideUploadError();
    const validation = validateFile(file);

    if (!validation.valid) {
      showUploadError(validation.message);
      resetFileInput();
      return;
    }

    currentFile = file;
    currentResumeId = null;
    resetJobMatchingState();
    resetSkillGapState();
    resetCareerRecommendationsState();
    resetResourceRecommendationsState();

    // Reset previous analysis results display when a new file is chosen
    if (extractedProfileCard) {
      extractedProfileCard.classList.add('hidden');
    }

    // Determine icon
    const isPdf = file.name.toLowerCase().endsWith('.pdf');
    fileFormatIcon.textContent = isPdf ? '📕' : '📘';

    // Populate UI details
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = `${formatBytes(file.size)} • ${isPdf ? 'PDF Document' : 'Word Document'}`;

    // Swap drop zone view for selected file view
    dropZone.classList.add('hidden');
    selectedFileInfo.classList.remove('hidden');

    // Update Overview stats
    overviewResumeStatus.textContent = 'File Selected';
    overviewResumeStatus.classList.remove('stat-muted');
    overviewScoreStatus.textContent = '—';
    overviewScoreStatus.classList.add('stat-muted');
    overviewGapStatus.textContent = '—';
    overviewGapStatus.classList.add('stat-muted');

    hideStatusMessage();
  }

  function showUploadError(message) {
    fileUploadErrorMessage.textContent = message;
    fileUploadError.classList.remove('hidden');
  }

  function hideUploadError() {
    fileUploadError.classList.add('hidden');
    fileUploadErrorMessage.textContent = '';
  }

  function resetFileInput() {
    currentFile = null;
    currentResumeId = null;
    currentSelectedRoleId = null;
    resetJobMatchingState();
    resetSkillGapState();
    resetCareerRecommendationsState();
    resetResourceRecommendationsState();
    resumeFileInput.value = '';
    dropZone.classList.remove('hidden');
    selectedFileInfo.classList.add('hidden');
    overviewResumeStatus.textContent = 'Not Uploaded';
    overviewResumeStatus.classList.add('stat-muted');
    overviewScoreStatus.textContent = '—';
    overviewScoreStatus.classList.add('stat-muted');
    overviewGapStatus.textContent = '—';
    overviewGapStatus.classList.add('stat-muted');
    if (extractedProfileCard) {
      extractedProfileCard.classList.add('hidden');
    }
  }

  // Dropzone click -> trigger input
  dropZone.addEventListener('click', () => {
    resumeFileInput.click();
  });

  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      resumeFileInput.click();
    }
  });

  // File input change
  resumeFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  // Drag and drop events
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-active');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleSelectedFile(dt.files[0]);
    }
  });

  // Remove file button
  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileInput();
    hideUploadError();
    hideStatusMessage();
  });

  // -------------------------------------------------------------------------
  // 3. Job Description & Inputs Handling
  // -------------------------------------------------------------------------
  function findTargetRoleMatch(titleQuery, matchesList) {
    if (!titleQuery || !matchesList || !Array.isArray(matchesList) || matchesList.length === 0) return null;
    const q = titleQuery.trim().toLowerCase();
    if (!q) return null;

    // 1. Exact title match (with clean titles)
    let match = matchesList.find(m => formatJobRoleTitle(m.job_role_title).toLowerCase() === q || m.job_role_title.toLowerCase() === q);
    if (match) return match;

    // 2. Substring match: catalog title contains query (e.g. "Data Analyst" matches "data analyst")
    match = matchesList.find(m => formatJobRoleTitle(m.job_role_title).toLowerCase().includes(q) || m.job_role_title.toLowerCase().includes(q));
    if (match) return match;

    // 3. Substring match: query contains catalog title
    match = matchesList.find(m => q.includes(formatJobRoleTitle(m.job_role_title).toLowerCase()) || q.includes(m.job_role_title.toLowerCase()));
    if (match) return match;

    // 4. Domain / keyword match across all 18 expanded roles
    const keywords = [
      'full stack', 'fullstack', 'frontend', 'front-end', 'backend', 'back-end', 'python',
      'java developer', 'java', 'sde', 'software development engineer', 'software engineer',
      'data analyst', 'data engineer', 'bi analyst', 'business intelligence', 'data', 'analyst',
      'qa engineer', 'software tester', 'automation test', 'tester', 'testing', 'qa',
      'devops', 'cloud', 'sre', 'site reliability',
      'cybersecurity', 'security analyst', 'security',
      'ui/ux', 'ui designer', 'ux designer', 'designer',
      'machine learning', 'ml engineer', 'ml',
      'business analyst', 'database developer', 'sql developer', 'database',
      'mobile app developer', 'mobile developer', 'mobile'
    ];
    for (const kw of keywords) {
      if (q.includes(kw)) {
        match = matchesList.find(m => formatJobRoleTitle(m.job_role_title).toLowerCase().includes(kw));
        if (match) return match;
      }
    }

    return null;
  }

  function updateDashboardOverview() {
    const userTarget = targetJobTitleInput ? targetJobTitleInput.value.trim() : '';
    const hasMatchingData = currentMatchingData && Array.isArray(currentMatchingData.matches) && currentMatchingData.matches.length > 0;

    // 1. Target Role card
    if (overviewRoleStatus) {
      if (userTarget.length > 0) {
        overviewRoleStatus.textContent = formatJobRoleTitle(userTarget);
        overviewRoleStatus.classList.remove('stat-muted');
      } else {
        overviewRoleStatus.textContent = 'None Specified';
        overviewRoleStatus.classList.add('stat-muted');
      }
    }

    // Determine target-job evaluation match
    let targetMatch = null;
    if (userTarget.length > 0 && hasMatchingData) {
      targetMatch = findTargetRoleMatch(userTarget, currentMatchingData.matches);
    }

    // Top alternative recommendation: highest-scoring role excluding the target role
    let topRec = null;
    if (hasMatchingData) {
      if (targetMatch) {
        topRec = currentMatchingData.matches.find(m => m.job_role_id !== targetMatch.job_role_id) || currentMatchingData.matches[0];
      } else {
        topRec = currentMatchingData.matches[0];
      }
    }

    // 2. Compatibility Score card
    if (overviewScoreStatus) {
      if (targetMatch) {
        overviewScoreStatus.textContent = `${targetMatch.match_score.toFixed(2)}%`;
        overviewScoreStatus.classList.remove('stat-muted');
        const cleanTargetTitle = formatJobRoleTitle(targetMatch.job_role_title);
        overviewScoreStatus.title = `Compatibility score for ${cleanTargetTitle}`;
        if (overviewScoreHint) {
          overviewScoreHint.textContent = `Target role: ${cleanTargetTitle}`;
        }
      } else {
        overviewScoreStatus.textContent = '—';
        overviewScoreStatus.classList.add('stat-muted');
        overviewScoreStatus.removeAttribute('title');
        if (overviewScoreHint) {
          if (!hasMatchingData) {
            overviewScoreHint.textContent = 'Awaiting analysis';
          } else if (userTarget.length > 0) {
            overviewScoreHint.textContent = 'Target role not in catalog';
          } else {
            overviewScoreHint.textContent = 'No target role specified';
          }
        }
      }
    }

    // 3. Identified Gaps card
    if (overviewGapStatus) {
      let targetGap = null;
      if (targetMatch && currentSkillGapData && Array.isArray(currentSkillGapData.role_gaps)) {
        targetGap = currentSkillGapData.role_gaps.find(r => r.job_role_id === targetMatch.job_role_id);
      }

      if (targetGap) {
        const critCount = targetGap.critical_missing_count !== undefined ? targetGap.critical_missing_count : 0;
        const secCount = targetGap.secondary_missing_count !== undefined ? targetGap.secondary_missing_count : 0;
        overviewGapStatus.textContent = `${critCount} Critical / ${secCount} Secondary`;
        overviewGapStatus.classList.remove('stat-muted');
        const cleanGapTitle = formatJobRoleTitle(targetGap.job_role_title);
        overviewGapStatus.title = `${cleanGapTitle}: ${critCount} Critical Gaps, ${secCount} Secondary Gaps`;
      } else {
        overviewGapStatus.textContent = '—';
        overviewGapStatus.classList.add('stat-muted');
        overviewGapStatus.removeAttribute('title');
      }
    }

    // 4. Top Match / Recommendation Hint
    if (overviewGapHint) {
      if (topRec) {
        const cleanRecTitle = formatJobRoleTitle(topRec.job_role_title);
        overviewGapHint.textContent = `Top Recommendation: ${cleanRecTitle} (${topRec.match_score.toFixed(1)}%)`;
        overviewGapHint.title = `Best recommended career role: ${cleanRecTitle} with ${topRec.match_score.toFixed(2)}% match`;
      } else {
        overviewGapHint.textContent = 'Pending resume evaluation';
        overviewGapHint.removeAttribute('title');
      }
    }
  }

  function refreshAllRoleSelectors() {
    if (currentMatchingData && Array.isArray(currentMatchingData.matches) && currentMatchingData.matches.length > 0) {
      renderJobMatchingButtons();
      if (selectedJobRoleId) renderSelectedRoleDetail(selectedJobRoleId);
    }
    if (currentSkillGapData && Array.isArray(currentSkillGapData.role_gaps) && currentSkillGapData.role_gaps.length > 0) {
      renderSkillGapButtons();
      if (selectedSkillGapRoleId) renderSelectedSkillGapDetail(selectedSkillGapRoleId);
    }
    if (currentCareerRecData && Array.isArray(currentCareerRecData.recommendations) && currentCareerRecData.recommendations.length > 0) {
      renderCareerRecButtons();
      if (selectedCareerRecRoleId) renderSelectedCareerRecDetail(selectedCareerRecRoleId);
    }
    if (currentResourceRecData && Array.isArray(currentResourceRecData.roles) && currentResourceRecData.roles.length > 0) {
      renderResourceRecButtons();
      if (selectedResourceRecRoleId) renderSelectedResourceRecDetail(selectedResourceRecRoleId);
    }
  }

  jobDescriptionInput.addEventListener('input', () => {
    const charCount = jobDescriptionInput.value.length;
    jobDescCharCount.textContent = `${charCount.toLocaleString()} character${charCount === 1 ? '' : 's'}`;
  });

  targetJobTitleInput.addEventListener('input', () => {
    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;

    if (targetRoleId && (!currentSelectedRoleId || currentSelectedRoleId === previousTargetRoleId)) {
      currentSelectedRoleId = targetRoleId;
      selectedJobRoleId = targetRoleId;
      selectedSkillGapRoleId = targetRoleId;
      selectedCareerRecRoleId = targetRoleId;
      selectedResourceRecRoleId = targetRoleId;
    }
    previousTargetRoleId = targetRoleId;

    updateDashboardOverview();
    refreshAllRoleSelectors();
  });

  // Clear inputs
  clearInputsBtn.addEventListener('click', () => {
    currentResumeId = null;
    currentResumeToken = null;
    resetFileInput();
    targetJobTitleInput.value = '';
    jobDescriptionInput.value = '';
    jobDescCharCount.textContent = '0 characters';
    isExpandedJobMatching = false;
    isExpandedSkillGap = false;
    isExpandedCareerRec = false;
    isExpandedResourceRec = false;
    previousTargetRoleId = null;
    updateDashboardOverview();
    refreshAllRoleSelectors();
    hideUploadError();
    hideStatusMessage();
  });

  // -------------------------------------------------------------------------
  // 4. Analysis Action (UI Validation & Ready State — No Fake Scores)
  // -------------------------------------------------------------------------
  function showStatusMessage(type, icon, textHtml) {
    analysisStatusMessage.className = `status-banner ${type}`;
    statusMessageIcon.textContent = icon;
    statusMessageText.innerHTML = textHtml;
    analysisStatusMessage.classList.remove('hidden');
    analysisStatusMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideStatusMessage() {
    analysisStatusMessage.classList.add('hidden');
    statusMessageText.innerHTML = '';
  }

  function formatExtractionSource(source) {
    switch (source) {
      case 'SKILLS_SECTION': return 'Skills';
      case 'PROJECTS': return 'Projects';
      case 'EXPERIENCE': return 'Experience';
      case 'EDUCATION': return 'Education';
      default: return 'Resume';
    }
  }

  function renderExtractedProfile(data) {
    if (!extractedProfileCard) return;

    // 1. Candidate Info
    const cand = data.candidate || {};
    profileCandidateName.textContent = cand.candidate_name || 'Not detected in resume';
    profileCandidateEmail.textContent = cand.candidate_email || 'Not detected';
    profileCandidatePhone.textContent = cand.candidate_phone || 'Not detected';
    profileSkillCount.textContent = `${data.skills ? data.skills.length : 0} catalog skills`;

    // 2. Verified Skills
    extractedSkillsList.innerHTML = '';
    if (data.skills && data.skills.length > 0) {
      data.skills.forEach(s => {
        const chip = document.createElement('span');
        chip.className = 'skill-chip';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = s.skill_name;
        chip.appendChild(nameSpan);

        const sourceSpan = document.createElement('span');
        sourceSpan.className = 'skill-chip-source';
        sourceSpan.textContent = formatExtractionSource(s.extraction_source);
        chip.appendChild(sourceSpan);

        extractedSkillsList.appendChild(chip);
      });
    } else {
      const emptyNotice = document.createElement('p');
      emptyNotice.className = 'empty-entity-notice';
      emptyNotice.textContent = 'No matching catalog skills detected in resume.';
      extractedSkillsList.appendChild(emptyNotice);
    }

    // 3. Unmatched Skills (if any)
    if (unmatchedSkillsSection && unmatchedSkillsList) {
      unmatchedSkillsList.innerHTML = '';
      if (data.unmatched_skills && data.unmatched_skills.length > 0) {
        data.unmatched_skills.forEach(name => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip unmatched';
          chip.textContent = name;
          unmatchedSkillsList.appendChild(chip);
        });
        unmatchedSkillsSection.classList.remove('hidden');
      } else {
        unmatchedSkillsSection.classList.add('hidden');
      }
    }

    // 4. Education
    extractedEducationList.innerHTML = '';
    if (data.education && data.education.length > 0) {
      data.education.forEach(e => {
        const item = document.createElement('div');
        item.className = 'entity-item-card';

        const header = document.createElement('div');
        header.className = 'entity-item-header';

        const title = document.createElement('span');
        title.className = 'entity-item-title';
        title.textContent = e.degree || 'Degree';
        header.appendChild(title);

        if (e.start_year || e.end_year) {
          const badge = document.createElement('span');
          badge.className = 'entity-item-badge';
          badge.textContent = `${e.start_year || ''} - ${e.end_year || 'Present'}`;
          header.appendChild(badge);
        }
        item.appendChild(header);

        const subtitle = document.createElement('div');
        subtitle.className = 'entity-item-subtitle';
        const subParts = [];
        if (e.institution) subParts.push(e.institution);
        if (e.field_of_study) subParts.push(e.field_of_study);
        if (e.grade_or_cgpa) subParts.push(`Score: ${e.grade_or_cgpa}`);
        subtitle.textContent = subParts.join(' • ');
        item.appendChild(subtitle);

        extractedEducationList.appendChild(item);
      });
    } else {
      const emptyNotice = document.createElement('p');
      emptyNotice.className = 'empty-entity-notice';
      emptyNotice.textContent = 'No explicit education records detected.';
      extractedEducationList.appendChild(emptyNotice);
    }

    // 5. Projects
    extractedProjectsList.innerHTML = '';
    if (data.projects && data.projects.length > 0) {
      data.projects.forEach(p => {
        const item = document.createElement('div');
        item.className = 'entity-item-card';

        const header = document.createElement('div');
        header.className = 'entity-item-header';
        const title = document.createElement('span');
        title.className = 'entity-item-title';
        title.textContent = p.title;
        header.appendChild(title);
        item.appendChild(header);

        if (p.technologies_used) {
          const tech = document.createElement('div');
          tech.className = 'entity-item-tech';
          tech.textContent = `Technologies: ${p.technologies_used}`;
          item.appendChild(tech);
        }

        if (p.description) {
          const desc = document.createElement('div');
          desc.className = 'entity-item-desc';
          desc.textContent = p.description;
          item.appendChild(desc);
        }

        extractedProjectsList.appendChild(item);
      });
    } else {
      const emptyNotice = document.createElement('p');
      emptyNotice.className = 'empty-entity-notice';
      emptyNotice.textContent = 'No explicit project entries detected.';
      extractedProjectsList.appendChild(emptyNotice);
    }

    // 6. Experience
    extractedExperienceList.innerHTML = '';
    if (data.experience && data.experience.length > 0) {
      data.experience.forEach(exp => {
        const item = document.createElement('div');
        item.className = 'entity-item-card';

        const header = document.createElement('div');
        header.className = 'entity-item-header';
        const title = document.createElement('span');
        title.className = 'entity-item-title';
        title.textContent = exp.role_title || 'Role';
        header.appendChild(title);

        if (exp.duration) {
          const badge = document.createElement('span');
          badge.className = 'entity-item-badge';
          badge.textContent = exp.duration;
          header.appendChild(badge);
        }
        item.appendChild(header);

        if (exp.organization) {
          const subtitle = document.createElement('div');
          subtitle.className = 'entity-item-subtitle';
          subtitle.textContent = exp.organization;
          item.appendChild(subtitle);
        }

        if (exp.description) {
          const desc = document.createElement('div');
          desc.className = 'entity-item-desc';
          desc.textContent = exp.description;
          item.appendChild(desc);
        }

        extractedExperienceList.appendChild(item);
      });
    } else {
      const emptyNotice = document.createElement('p');
      emptyNotice.className = 'empty-entity-notice';
      emptyNotice.textContent = 'No work or practical experience entries detected.';
      extractedExperienceList.appendChild(emptyNotice);
    }

    extractedProfileCard.classList.remove('hidden');
    extractedProfileCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // -------------------------------------------------------------------------
  // 4b. Job Matching Section Integration
  // -------------------------------------------------------------------------
  function resetJobMatchingState() {
    currentMatchingRequestId++;
    currentMatchingData = null;
    selectedJobRoleId = null;

    if (jobMatchingLoadingCard) jobMatchingLoadingCard.classList.add('hidden');
    if (jobMatchingErrorCard) jobMatchingErrorCard.classList.add('hidden');
    if (jobMatchingResultsCard) jobMatchingResultsCard.classList.add('hidden');
    if (jobMatchingEmptyCard) jobMatchingEmptyCard.classList.remove('hidden');

    updateDashboardOverview();
  }

  function renderSelectedRoleDetail(jobRoleId) {
    if (!currentMatchingData || !currentMatchingData.matches || currentMatchingData.matches.length === 0) return;

    selectedJobRoleId = jobRoleId;
    const matchIdx = currentMatchingData.matches.findIndex(m => m.job_role_id === jobRoleId);
    const roleMatch = matchIdx >= 0 ? currentMatchingData.matches[matchIdx] : currentMatchingData.matches[0];
    const rank = matchIdx >= 0 ? matchIdx + 1 : 1;

    // 1. Update active tab style on selector buttons
    if (jobRoleSelectorList) {
      const buttons = jobRoleSelectorList.querySelectorAll('button');
      buttons.forEach(btn => {
        if (btn.classList.contains('more-toggle-btn')) return;
        const btnRoleId = parseInt(btn.getAttribute('data-role-id'), 10);
        if (btnRoleId === roleMatch.job_role_id) {
          btn.className = 'btn btn-primary';
        } else {
          btn.className = 'btn btn-secondary';
        }
      });
    }

    // 2. Header rank badge
    if (jobMatchingRankBadge) {
      const targetMatch = getTargetRoleMatch();
      const isTarget = targetMatch && roleMatch.job_role_id === targetMatch.job_role_id;
      const prefix = isTarget ? 'Target Role • ' : '';
      jobMatchingRankBadge.textContent = `${prefix}Rank #${rank} • ${roleMatch.match_score.toFixed(1)}% Match`;
    }

    // 3. Meta items
    if (matchRoleTitle) matchRoleTitle.textContent = formatJobRoleTitle(roleMatch.job_role_title);
    if (matchRoleDomain) matchRoleDomain.textContent = `${roleMatch.domain || 'General'} • ${roleMatch.experience_level || 'ENTRY_LEVEL'}`;
    if (matchScoreValue) matchScoreValue.textContent = `${roleMatch.match_score.toFixed(2)}%`;
    if (matchRequiredCoverage) {
      const reqMatchedCount = (roleMatch.matched_skills || []).filter(s => s.importance === 'REQUIRED').length;
      const reqTotalCount = reqMatchedCount + (roleMatch.missing_required_skills || []).length;
      matchRequiredCoverage.textContent = `${roleMatch.required_skills_match_percentage.toFixed(2)}% (${reqMatchedCount}/${reqTotalCount} required)`;
    }

    // 4. Dynamic explanation
    if (matchExplanationText) {
      matchExplanationText.textContent = roleMatch.explanation || 'No explanation available.';
    }

    // 5. Matched skills
    if (matchedSkillsCountBadge) {
      matchedSkillsCountBadge.textContent = `(${roleMatch.matched_skills ? roleMatch.matched_skills.length : 0})`;
    }
    if (matchedSkillsChipsList) {
      matchedSkillsChipsList.innerHTML = '';
      if (roleMatch.matched_skills && roleMatch.matched_skills.length > 0) {
        roleMatch.matched_skills.forEach(s => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = s.skill_name;
          chip.appendChild(nameSpan);

          const sourceSpan = document.createElement('span');
          sourceSpan.className = 'skill-chip-source';
          sourceSpan.textContent = `${formatExtractionSource(s.extraction_source)} • wt: ${s.weight.toFixed(1)}`;
          chip.appendChild(sourceSpan);

          matchedSkillsChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No matching catalog skills detected for this role.';
        matchedSkillsChipsList.appendChild(emptyNotice);
      }
    }

    // 6. Missing Required skills
    if (missingRequiredCountBadge) {
      missingRequiredCountBadge.textContent = `(${roleMatch.missing_required_skills ? roleMatch.missing_required_skills.length : 0})`;
    }
    if (missingRequiredChipsList) {
      missingRequiredChipsList.innerHTML = '';
      if (roleMatch.missing_required_skills && roleMatch.missing_required_skills.length > 0) {
        roleMatch.missing_required_skills.forEach(s => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip unmatched';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = s.skill_name;
          chip.appendChild(nameSpan);

          const wtSpan = document.createElement('span');
          wtSpan.className = 'skill-chip-source';
          wtSpan.style.color = '#ef4444';
          wtSpan.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
          wtSpan.textContent = `Required • wt: ${s.weight.toFixed(1)}`;
          chip.appendChild(wtSpan);

          missingRequiredChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'All required catalog skills are verified — 100% core coverage!';
        missingRequiredChipsList.appendChild(emptyNotice);
      }
    }

    // 7. Missing Preferred skills
    if (missingPreferredCountBadge) {
      missingPreferredCountBadge.textContent = `(${roleMatch.missing_preferred_skills ? roleMatch.missing_preferred_skills.length : 0})`;
    }
    if (missingPreferredChipsList) {
      missingPreferredChipsList.innerHTML = '';
      if (roleMatch.missing_preferred_skills && roleMatch.missing_preferred_skills.length > 0) {
        roleMatch.missing_preferred_skills.forEach(s => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip unmatched';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = s.skill_name;
          chip.appendChild(nameSpan);

          const wtSpan = document.createElement('span');
          wtSpan.className = 'skill-chip-source';
          wtSpan.style.color = '#f59e0b';
          wtSpan.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
          wtSpan.textContent = `Preferred • wt: ${s.weight.toFixed(1)}`;
          chip.appendChild(wtSpan);

          missingPreferredChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No missing preferred skills identified for this role.';
        missingPreferredChipsList.appendChild(emptyNotice);
      }
    }

    // 8. Scoring Breakdown Box
    const bd = roleMatch.score_breakdown || {};
    if (matchFormulaText) matchFormulaText.textContent = bd.formula || '(matched_weight / total_role_weight) * 100';
    if (matchMatchedWeight) matchMatchedWeight.textContent = `${(bd.matched_weight !== undefined ? bd.matched_weight : 0).toFixed(2)} pts`;
    if (matchTotalWeight) matchTotalWeight.textContent = `${(bd.total_role_weight !== undefined ? bd.total_role_weight : 0).toFixed(2)} pts`;
    if (matchRequiredWeightRatio) {
      const reqMatched = (bd.required_weight_matched !== undefined ? bd.required_weight_matched : 0).toFixed(2);
      const reqTotal = (bd.required_weight_total !== undefined ? bd.required_weight_total : 0).toFixed(2);
      matchRequiredWeightRatio.textContent = `${reqMatched} / ${reqTotal} pts`;
    }
  }

  function renderJobMatching(data) {
    if (!jobMatchingResultsCard) return;

    currentMatchingData = data;
    const matches = data.matches || [];

    if (matches.length === 0) {
      resetJobMatchingState();
      return;
    }

    // Hide empty, loading, and error states; show results card
    if (jobMatchingEmptyCard) jobMatchingEmptyCard.classList.add('hidden');
    if (jobMatchingLoadingCard) jobMatchingLoadingCard.classList.add('hidden');
    if (jobMatchingErrorCard) jobMatchingErrorCard.classList.add('hidden');
    jobMatchingResultsCard.classList.remove('hidden');

    // 1. Determine active role to select: prioritize shared selected role, then target role match, fallback to Rank 1
    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;

    let defaultRoleId = (currentSelectedRoleId && matches.some(m => m.job_role_id === currentSelectedRoleId))
      ? currentSelectedRoleId
      : (targetRoleId || matches[0].job_role_id);

    selectedJobRoleId = defaultRoleId;
    if (!currentSelectedRoleId) {
      currentSelectedRoleId = defaultRoleId;
    }

    // 2. Populate role selector buttons (Target Role First + Top 5 Alternatives + More/Less)
    renderJobMatchingButtons();

    // 3. Render details for selected role
    renderSelectedRoleDetail(selectedJobRoleId);

    // 4. Update Overview dashboard metrics
    updateDashboardOverview();
  }

  function renderJobMatchingButtons() {
    if (!jobRoleSelectorList || !currentMatchingData || !currentMatchingData.matches) return;

    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;
    const displayedMatches = buildSectionRoleDisplayList(
      currentMatchingData.matches,
      isExpandedJobMatching,
      targetRoleId,
      selectedJobRoleId
    );

    jobRoleSelectorList.innerHTML = '';
    displayedMatches.forEach(roleMatch => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-role-id', String(roleMatch.job_role_id));
      btn.className = (roleMatch.job_role_id === selectedJobRoleId) ? 'btn btn-primary' : 'btn btn-secondary';
      btn.style.fontSize = '0.82rem';
      btn.style.padding = '6px 12px';

      if (targetRoleId && roleMatch.job_role_id === targetRoleId) {
        const targetBadge = document.createElement('span');
        targetBadge.className = 'role-target-badge';
        targetBadge.textContent = 'Target';
        btn.appendChild(targetBadge);
      }

      const titleSpan = document.createElement('span');
      titleSpan.textContent = formatJobRoleTitle(roleMatch.job_role_title);
      btn.appendChild(titleSpan);

      const scoreBadge = document.createElement('span');
      scoreBadge.style.fontSize = '0.72rem';
      scoreBadge.style.fontWeight = '700';
      scoreBadge.style.opacity = '0.9';
      scoreBadge.style.marginLeft = '6px';
      scoreBadge.textContent = `${roleMatch.match_score.toFixed(1)}%`;
      btn.appendChild(scoreBadge);

      btn.addEventListener('click', () => {
        selectCareerRole(roleMatch.job_role_id, { source: 'job-matching' });
      });

      jobRoleSelectorList.appendChild(btn);
    });

    // More / Less Toggle Button
    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.className = 'btn btn-secondary more-toggle-btn';
    moreBtn.textContent = isExpandedJobMatching ? 'Less ▴' : 'More ▾';
    moreBtn.title = isExpandedJobMatching ? 'Show top roles' : 'Show all 18 roles';
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      isExpandedJobMatching = !isExpandedJobMatching;
      renderJobMatchingButtons();
    });
    jobRoleSelectorList.appendChild(moreBtn);
  }

  async function fetchAndRenderJobMatching(resumeId) {
    if (!resumeId) {
      resetJobMatchingState();
      return;
    }

    const requestId = ++currentMatchingRequestId;

    // Show loading state, hide empty, error, and results
    if (jobMatchingEmptyCard) jobMatchingEmptyCard.classList.add('hidden');
    if (jobMatchingErrorCard) jobMatchingErrorCard.classList.add('hidden');
    if (jobMatchingResultsCard) jobMatchingResultsCard.classList.add('hidden');
    if (jobMatchingLoadingCard) jobMatchingLoadingCard.classList.remove('hidden');

    try {
      let res;
      try {
        res = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/matches`, {
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to matching API at ${API_BASE_URL}. Ensure backend is active.`);
      }

      // Check if another request superseded this one
      if (requestId !== currentMatchingRequestId) return;

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Matching calculation failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      if (requestId !== currentMatchingRequestId) return;

      if (jobMatchingLoadingCard) jobMatchingLoadingCard.classList.add('hidden');
      renderJobMatching(data);

    } catch (err) {
      if (requestId !== currentMatchingRequestId) return;

      if (jobMatchingLoadingCard) jobMatchingLoadingCard.classList.add('hidden');
      if (jobMatchingResultsCard) jobMatchingResultsCard.classList.add('hidden');
      if (jobMatchingErrorCard) {
        if (jobMatchingErrorMessage) {
          jobMatchingErrorMessage.textContent = err.message || 'Failed to calculate job matches.';
        }
        jobMatchingErrorCard.classList.remove('hidden');
      }
      if (overviewScoreStatus) {
        overviewScoreStatus.textContent = '—';
        overviewScoreStatus.classList.add('stat-muted');
      }
    }
  }

  if (jobMatchingRetryBtn) {
    jobMatchingRetryBtn.addEventListener('click', () => {
      if (currentResumeId) {
        fetchAndRenderJobMatching(currentResumeId);
      }
    });
  }

  // -------------------------------------------------------------------------
  // 4c. Skill Gap Analysis Section Integration
  // -------------------------------------------------------------------------
  function updateOverviewGapStatus(data) {
    updateDashboardOverview();
  }

  function resetSkillGapState() {
    currentSkillGapRequestId++;
    currentSkillGapData = null;
    selectedSkillGapRoleId = null;
    isSkillGapAnalyzing = false;

    if (skillGapLoadingCard) skillGapLoadingCard.classList.add('hidden');
    if (skillGapErrorCard) skillGapErrorCard.classList.add('hidden');
    if (skillGapResultsCard) skillGapResultsCard.classList.add('hidden');
    if (skillGapEmptyCard) skillGapEmptyCard.classList.remove('hidden');

    updateDashboardOverview();
  }

  function renderSelectedSkillGapDetail(jobRoleId) {
    if (!currentSkillGapData || !currentSkillGapData.role_gaps || currentSkillGapData.role_gaps.length === 0) return;

    selectedSkillGapRoleId = jobRoleId;
    const roleGaps = currentSkillGapData.role_gaps;
    const role = roleGaps.find(r => r.job_role_id === jobRoleId) || roleGaps[0];

    // 1. Update active tab style on selector buttons
    if (skillGapRoleSelectorList) {
      const buttons = skillGapRoleSelectorList.querySelectorAll('button');
      buttons.forEach(btn => {
        if (btn.classList.contains('more-toggle-btn')) return;
        const btnRoleId = parseInt(btn.getAttribute('data-role-id'), 10);
        if (btnRoleId === role.job_role_id) {
          btn.className = 'btn btn-primary';
        } else {
          btn.className = 'btn btn-secondary';
        }
      });
    }

    // 2. Header rank badge
    if (skillGapRankBadge) {
      let rankPrefix = '';
      if (currentMatchingData && currentMatchingData.matches && currentMatchingData.matches.length > 0) {
        const mIdx = currentMatchingData.matches.findIndex(m => m.job_role_id === role.job_role_id);
        if (mIdx >= 0) {
          rankPrefix = `Rank #${mIdx + 1} • `;
        }
      }
      const targetMatch = getTargetRoleMatch();
      const isTarget = targetMatch && role.job_role_id === targetMatch.job_role_id;
      const targetPrefix = isTarget ? 'Target Role • ' : '';
      skillGapRankBadge.textContent = `${targetPrefix}${rankPrefix}${role.compatibility_score.toFixed(1)}% Match • ${role.critical_missing_count} Critical Gaps`;
    }

    // 3. Meta items
    if (gapRoleTitle) gapRoleTitle.textContent = formatJobRoleTitle(role.job_role_title);
    if (gapRoleDomain) gapRoleDomain.textContent = `${role.domain || 'General'} • ${role.experience_level || 'ENTRY_LEVEL'}`;
    if (gapScoreValue) gapScoreValue.textContent = `${role.compatibility_score.toFixed(2)}%`;
    if (gapTechScoreValue) gapTechScoreValue.textContent = `${role.technical_skill_score.toFixed(2)}%`;
    if (gapPossessedCount) gapPossessedCount.textContent = `${role.possessed_skills_count} / ${role.total_role_skills_count} skills`;
    if (gapTotalMissingCount) gapTotalMissingCount.textContent = `${role.missing_skills_count} gaps (${role.critical_missing_count} critical, ${role.secondary_missing_count} secondary)`;

    // 4. Dynamic explanation
    if (gapExplanationText) {
      gapExplanationText.textContent = role.explanation || 'No explanation available.';
    }

    // 5. Critical Missing Skills
    if (gapCriticalCountBadge) {
      gapCriticalCountBadge.textContent = `(${role.critical_missing_skills ? role.critical_missing_skills.length : 0})`;
    }
    if (gapCriticalSkillsList) {
      gapCriticalSkillsList.innerHTML = '';
      if (role.critical_missing_skills && role.critical_missing_skills.length > 0) {
        role.critical_missing_skills.forEach(gap => {
          const card = document.createElement('div');
          card.className = 'entity-item-card';
          card.style.marginBottom = '8px';
          card.style.padding = '10px 12px';

          const hdr = document.createElement('div');
          hdr.className = 'entity-item-header';
          hdr.style.marginBottom = '4px';

          const title = document.createElement('span');
          title.className = 'entity-item-title';
          title.textContent = gap.skill_name;
          hdr.appendChild(title);

          const badge = document.createElement('span');
          badge.className = 'entity-item-badge';
          badge.style.fontSize = '0.72rem';
          badge.style.fontWeight = '700';
          badge.style.color = '#ef4444';
          badge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
          badge.style.border = '1px solid rgba(239, 68, 68, 0.2)';
          badge.textContent = `Required • wt: ${gap.weight.toFixed(1)}`;
          hdr.appendChild(badge);

          card.appendChild(hdr);

          if (gap.reason) {
            const desc = document.createElement('div');
            desc.className = 'entity-item-desc';
            desc.style.fontSize = '0.78rem';
            desc.textContent = gap.reason;
            card.appendChild(desc);
          }

          gapCriticalSkillsList.appendChild(card);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'All required competencies are verified — zero critical gaps!';
        gapCriticalSkillsList.appendChild(emptyNotice);
      }
    }

    // 6. Secondary Missing Skills
    if (gapSecondaryCountBadge) {
      gapSecondaryCountBadge.textContent = `(${role.secondary_missing_skills ? role.secondary_missing_skills.length : 0})`;
    }
    if (gapSecondarySkillsList) {
      gapSecondarySkillsList.innerHTML = '';
      if (role.secondary_missing_skills && role.secondary_missing_skills.length > 0) {
        role.secondary_missing_skills.forEach(gap => {
          const card = document.createElement('div');
          card.className = 'entity-item-card';
          card.style.marginBottom = '8px';
          card.style.padding = '10px 12px';

          const hdr = document.createElement('div');
          hdr.className = 'entity-item-header';
          hdr.style.marginBottom = '4px';

          const title = document.createElement('span');
          title.className = 'entity-item-title';
          title.textContent = gap.skill_name;
          hdr.appendChild(title);

          const badge = document.createElement('span');
          badge.className = 'entity-item-badge';
          badge.style.fontSize = '0.72rem';
          badge.style.fontWeight = '700';
          badge.style.color = '#f59e0b';
          badge.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
          badge.style.border = '1px solid rgba(245, 158, 11, 0.2)';
          badge.textContent = `Preferred • wt: ${gap.weight.toFixed(1)}`;
          hdr.appendChild(badge);

          card.appendChild(hdr);

          if (gap.reason) {
            const desc = document.createElement('div');
            desc.className = 'entity-item-desc';
            desc.style.fontSize = '0.78rem';
            desc.textContent = gap.reason;
            card.appendChild(desc);
          }

          gapSecondarySkillsList.appendChild(card);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No secondary or preferred skill gaps identified for this role.';
        gapSecondarySkillsList.appendChild(emptyNotice);
      }
    }

    // 7. Possessed Skills for this Role
    if (gapPossessedCountBadge) {
      gapPossessedCountBadge.textContent = `(${role.possessed_skills ? role.possessed_skills.length : 0})`;
    }
    if (gapPossessedChipsList) {
      gapPossessedChipsList.innerHTML = '';
      if (role.possessed_skills && role.possessed_skills.length > 0) {
        role.possessed_skills.forEach(s => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = s.skill_name;
          chip.appendChild(nameSpan);

          const sourceSpan = document.createElement('span');
          sourceSpan.className = 'skill-chip-source';
          sourceSpan.textContent = `${formatExtractionSource(s.extraction_source)} • wt: ${s.weight.toFixed(1)}`;
          chip.appendChild(sourceSpan);

          gapPossessedChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No overlapping catalog skills possessed for this role.';
        gapPossessedChipsList.appendChild(emptyNotice);
      }
    }
  }

  function renderSkillGaps(data) {
    if (!skillGapResultsCard) return;

    currentSkillGapData = data;
    const roleGaps = data.role_gaps || [];

    if (roleGaps.length === 0) {
      resetSkillGapState();
      return;
    }

    // Hide empty, loading, and error states; show results card
    if (skillGapEmptyCard) skillGapEmptyCard.classList.add('hidden');
    if (skillGapLoadingCard) skillGapLoadingCard.classList.add('hidden');
    if (skillGapErrorCard) skillGapErrorCard.classList.add('hidden');
    skillGapResultsCard.classList.remove('hidden');

    // 1. Determine active role to select: prioritize shared selected role, then target role match, fallback to top match / first role
    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;

    let defaultRoleId = (currentSelectedRoleId && roleGaps.some(r => r.job_role_id === currentSelectedRoleId))
      ? currentSelectedRoleId
      : (targetRoleId || (currentMatchingData && currentMatchingData.matches && currentMatchingData.matches[0].job_role_id) || roleGaps[0].job_role_id);

    selectedSkillGapRoleId = defaultRoleId;
    if (!currentSelectedRoleId && defaultRoleId) {
      currentSelectedRoleId = defaultRoleId;
    }

    // 2. Populate role selector buttons (Target Role First + Top 5 Alternatives + More/Less)
    renderSkillGapButtons();

    // 3. Render details for selected role
    renderSelectedSkillGapDetail(selectedSkillGapRoleId);

    // 4. Update overview metric
    updateOverviewGapStatus(data);
  }

  function renderSkillGapButtons() {
    if (!skillGapRoleSelectorList || !currentSkillGapData || !currentSkillGapData.role_gaps) return;

    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;
    const displayedGaps = buildSectionRoleDisplayList(
      currentSkillGapData.role_gaps,
      isExpandedSkillGap,
      targetRoleId,
      selectedSkillGapRoleId
    );

    skillGapRoleSelectorList.innerHTML = '';
    displayedGaps.forEach(rg => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-role-id', String(rg.job_role_id));
      btn.className = (rg.job_role_id === selectedSkillGapRoleId) ? 'btn btn-primary' : 'btn btn-secondary';
      btn.style.fontSize = '0.82rem';
      btn.style.padding = '6px 12px';

      if (targetRoleId && rg.job_role_id === targetRoleId) {
        const targetBadge = document.createElement('span');
        targetBadge.className = 'role-target-badge';
        targetBadge.textContent = 'Target';
        btn.appendChild(targetBadge);
      }

      const titleSpan = document.createElement('span');
      titleSpan.textContent = formatJobRoleTitle(rg.job_role_title);
      btn.appendChild(titleSpan);

      const gapBadge = document.createElement('span');
      gapBadge.style.fontSize = '0.72rem';
      gapBadge.style.fontWeight = '700';
      gapBadge.style.opacity = '0.9';
      gapBadge.style.marginLeft = '6px';
      gapBadge.textContent = `${rg.critical_missing_count} crit / ${rg.secondary_missing_count} sec`;
      btn.appendChild(gapBadge);

      btn.addEventListener('click', () => {
        selectCareerRole(rg.job_role_id, { source: 'skill-gap' });
      });

      skillGapRoleSelectorList.appendChild(btn);
    });

    // More / Less Toggle Button
    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.className = 'btn btn-secondary more-toggle-btn';
    moreBtn.textContent = isExpandedSkillGap ? 'Less ▴' : 'More ▾';
    moreBtn.title = isExpandedSkillGap ? 'Show top roles' : 'Show all 18 roles';
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      isExpandedSkillGap = !isExpandedSkillGap;
      renderSkillGapButtons();
    });
    skillGapRoleSelectorList.appendChild(moreBtn);
  }

  async function fetchAndRenderSkillGaps(resumeId) {
    if (!resumeId) {
      resetSkillGapState();
      return;
    }

    // Reuse cached results if already available for this exact resume
    if (currentSkillGapData && currentSkillGapData.resume_id === resumeId) {
      renderSkillGaps(currentSkillGapData);
      return;
    }

    if (isSkillGapAnalyzing) {
      return; // prevent duplicate concurrent analysis runs
    }

    const requestId = ++currentSkillGapRequestId;

    // Show loading state, hide empty, error, and results
    if (skillGapEmptyCard) skillGapEmptyCard.classList.add('hidden');
    if (skillGapErrorCard) skillGapErrorCard.classList.add('hidden');
    if (skillGapResultsCard) skillGapResultsCard.classList.add('hidden');
    if (skillGapLoadingCard) skillGapLoadingCard.classList.remove('hidden');

    try {
      // 1. Prefer retrieving existing persisted results with GET first
      let getRes;
      try {
        getRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/skill-gaps`, {
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Skill Gap API at ${API_BASE_URL}. Ensure backend is active.`);
      }

      if (requestId !== currentSkillGapRequestId) return;

      if (getRes.ok) {
        const data = await getRes.json();
        if (requestId !== currentSkillGapRequestId) return;
        if (skillGapLoadingCard) skillGapLoadingCard.classList.add('hidden');
        renderSkillGaps(data);
        return;
      }

      // Check if GET 404 indicates analysis hasn't been generated yet
      let needsGeneration = false;
      let errDetail = '';
      try {
        const errJson = await getRes.json();
        errDetail = errJson.detail || '';
      } catch (_) {}

      // Backend returns 404 with "not been performed" or "analyze first" when analysis sessions do not yet exist
      if (getRes.status === 404 && (
        errDetail.toLowerCase().includes('not been performed') ||
        errDetail.toLowerCase().includes('analyze first')
      )) {
        needsGeneration = true;
      }

      if (!needsGeneration) {
        // Do NOT treat unrelated server errors (400 unanalyzed resume, 404 nonexistent resume, 500) as needing generation
        throw new Error(errDetail || `Skill gap retrieval failed with HTTP ${getRes.status}`);
      }

      // 2. Results need generation: call POST /api/resumes/{resume_id}/skill-gaps/analyze
      isSkillGapAnalyzing = true;
      let postRes;
      try {
        postRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/skill-gaps/analyze`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Skill Gap Analysis endpoint at ${API_BASE_URL}.`);
      } finally {
        isSkillGapAnalyzing = false;
      }

      if (requestId !== currentSkillGapRequestId) return;

      if (!postRes.ok) {
        const postErrJson = await postRes.json().catch(() => ({}));
        throw new Error(postErrJson.detail || `Skill gap analysis generation failed with HTTP ${postRes.status}`);
      }

      const generatedData = await postRes.json();
      if (requestId !== currentSkillGapRequestId) return;

      if (skillGapLoadingCard) skillGapLoadingCard.classList.add('hidden');
      renderSkillGaps(generatedData);

    } catch (err) {
      if (requestId !== currentSkillGapRequestId) return;

      if (skillGapLoadingCard) skillGapLoadingCard.classList.add('hidden');
      if (skillGapResultsCard) skillGapResultsCard.classList.add('hidden');
      if (skillGapErrorCard) {
        if (skillGapErrorMessage) {
          skillGapErrorMessage.textContent = err.message || 'Failed to process skill gap analysis.';
        }
        skillGapErrorCard.classList.remove('hidden');
      }

      if (overviewGapStatus) {
        overviewGapStatus.textContent = '—';
        overviewGapStatus.classList.add('stat-muted');
        overviewGapStatus.removeAttribute('title');
      }
      if (overviewGapHint) {
        overviewGapHint.textContent = 'Pending resume evaluation';
      }
    }
  }

  if (skillGapRetryBtn) {
    skillGapRetryBtn.addEventListener('click', () => {
      if (currentResumeId) {
        fetchAndRenderSkillGaps(currentResumeId);
      }
    });
  }

  // -------------------------------------------------------------------------
  // 4d. Career Recommendations Section Integration
  // -------------------------------------------------------------------------
  function formatFitLevel(fitLevel) {
    switch (fitLevel) {
      case 'STRONG_MATCH':
        return { text: 'Strong Fit', color: 'var(--color-mint, #10b981)', bg: 'var(--color-mint-light, rgba(16, 185, 129, 0.1))', border: 'var(--color-mint-border, rgba(16, 185, 129, 0.25))' };
      case 'MODERATE_MATCH':
        return { text: 'Moderate Fit', color: 'var(--accent-purple, #a855f7)', bg: 'var(--accent-purple-light, rgba(168, 85, 247, 0.1))', border: 'var(--accent-purple-border, rgba(168, 85, 247, 0.25))' };
      case 'POTENTIAL_GROWTH':
        return { text: 'Growth Path', color: 'var(--color-warning, #f59e0b)', bg: 'var(--color-warning-light, rgba(245, 158, 11, 0.1))', border: 'var(--color-warning-border, rgba(245, 158, 11, 0.25))' };
      case 'NO_MATCH':
      default:
        return { text: 'No Overlap', color: 'var(--text-muted, #64748b)', bg: 'var(--bg-card-subtle, #f8fafc)', border: 'var(--border-color, #e2e8f0)' };
    }
  }

  function resetCareerRecommendationsState() {
    currentCareerRecRequestId++;
    currentCareerRecData = null;
    selectedCareerRecRoleId = null;
    isCareerRecAnalyzing = false;

    if (careerRecLoadingCard) careerRecLoadingCard.classList.add('hidden');
    if (careerRecErrorCard) careerRecErrorCard.classList.add('hidden');
    if (careerRecResultsCard) careerRecResultsCard.classList.add('hidden');
    if (careerRecEmptyCard) careerRecEmptyCard.classList.remove('hidden');
  }

  function renderSelectedCareerRecDetail(jobRoleId) {
    if (!currentCareerRecData || !currentCareerRecData.recommendations || currentCareerRecData.recommendations.length === 0) return;

    selectedCareerRecRoleId = jobRoleId;
    const recs = currentCareerRecData.recommendations;
    const rec = recs.find(r => r.job_role_id === jobRoleId) || recs[0];

    // 1. Update active tab style on selector buttons
    if (careerRecRoleSelectorList) {
      const buttons = careerRecRoleSelectorList.querySelectorAll('button');
      buttons.forEach(btn => {
        if (btn.classList.contains('more-toggle-btn')) return;
        const btnRoleId = parseInt(btn.getAttribute('data-role-id'), 10);
        if (btnRoleId === rec.job_role_id) {
          btn.className = 'btn btn-primary';
        } else {
          btn.className = 'btn btn-secondary';
        }
      });
    }

    // 2. Header top badge
    if (careerRecTopBadge) {
      const targetMatch = getTargetRoleMatch();
      const isTarget = targetMatch && rec.job_role_id === targetMatch.job_role_id;
      const targetPrefix = isTarget ? 'Target Role • ' : '';
      careerRecTopBadge.textContent = `${targetPrefix}Rank #${rec.rank} • ${rec.match_percentage.toFixed(1)}% Match`;
    }

    // 3. Meta items
    if (recRoleTitle) recRoleTitle.textContent = formatJobRoleTitle(rec.job_role_title);
    if (recRoleDomain) recRoleDomain.textContent = `${rec.domain || 'General'} • ${rec.experience_level || 'ENTRY_LEVEL'}`;
    if (recMatchScoreValue) recMatchScoreValue.textContent = `${rec.match_percentage.toFixed(2)}%`;
    if (recTechScoreValue) recTechScoreValue.textContent = `${rec.technical_skill_score.toFixed(2)}%`;
    if (recRankValue) recRankValue.textContent = `Rank #${rec.rank} of ${currentCareerRecData.total_recommendations}`;

    if (recFitLevelBadge) {
      const fit = formatFitLevel(rec.fit_level);
      recFitLevelBadge.textContent = fit.text;
      recFitLevelBadge.style.color = fit.color;
      recFitLevelBadge.style.backgroundColor = fit.bg;
      recFitLevelBadge.style.border = `1px solid ${fit.border}`;
      recFitLevelBadge.style.padding = '2px 8px';
      recFitLevelBadge.style.borderRadius = '9999px';
      recFitLevelBadge.style.fontSize = '0.78rem';
      recFitLevelBadge.style.fontWeight = '600';
    }

    // 4. Dynamic explanation / rationale
    if (recRationaleText) {
      recRationaleText.textContent = rec.rationale || 'No rationale available.';
    }

    // 5. Matched Verified Skills
    if (recMatchedSkillsCountBadge) {
      recMatchedSkillsCountBadge.textContent = `(${rec.matched_skills ? rec.matched_skills.length : 0})`;
    }
    if (recMatchedChipsList) {
      recMatchedChipsList.innerHTML = '';
      if (rec.matched_skills && rec.matched_skills.length > 0) {
        rec.matched_skills.forEach(skillName => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = skillName;
          chip.appendChild(nameSpan);

          recMatchedChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No matching catalog skills possessed for this role.';
        recMatchedChipsList.appendChild(emptyNotice);
      }
    }

    // 6. Critical Missing Skills (Required)
    if (recCriticalMissingCountBadge) {
      recCriticalMissingCountBadge.textContent = `(${rec.missing_required_skills ? rec.missing_required_skills.length : 0})`;
    }
    if (recCriticalChipsList) {
      recCriticalChipsList.innerHTML = '';
      if (rec.missing_required_skills && rec.missing_required_skills.length > 0) {
        rec.missing_required_skills.forEach(skillName => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip unmatched';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = skillName;
          chip.appendChild(nameSpan);

          const tagSpan = document.createElement('span');
          tagSpan.className = 'skill-chip-source';
          tagSpan.style.color = '#ef4444';
          tagSpan.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
          tagSpan.textContent = 'Critical Gap';
          chip.appendChild(tagSpan);

          recCriticalChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'All required competencies are verified — zero critical missing skills!';
        recCriticalChipsList.appendChild(emptyNotice);
      }
    }

    // 7. Secondary Missing Skills (Preferred)
    if (recSecondaryMissingCountBadge) {
      recSecondaryMissingCountBadge.textContent = `(${rec.missing_preferred_skills ? rec.missing_preferred_skills.length : 0})`;
    }
    if (recSecondaryChipsList) {
      recSecondaryChipsList.innerHTML = '';
      if (rec.missing_preferred_skills && rec.missing_preferred_skills.length > 0) {
        rec.missing_preferred_skills.forEach(skillName => {
          const chip = document.createElement('span');
          chip.className = 'skill-chip unmatched';

          const nameSpan = document.createElement('span');
          nameSpan.textContent = skillName;
          chip.appendChild(nameSpan);

          const tagSpan = document.createElement('span');
          tagSpan.className = 'skill-chip-source';
          tagSpan.style.color = '#f59e0b';
          tagSpan.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
          tagSpan.textContent = 'Secondary Gap';
          chip.appendChild(tagSpan);

          recSecondaryChipsList.appendChild(chip);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No secondary or preferred skill gaps identified for this role.';
        recSecondaryChipsList.appendChild(emptyNotice);
      }
    }
  }

  function renderCareerRecommendations(data) {
    if (!careerRecResultsCard) return;

    currentCareerRecData = data;
    const recs = data.recommendations || [];

    if (recs.length === 0) {
      resetCareerRecommendationsState();
      return;
    }

    // Hide empty, loading, error states; show results
    if (careerRecEmptyCard) careerRecEmptyCard.classList.add('hidden');
    if (careerRecLoadingCard) careerRecLoadingCard.classList.add('hidden');
    if (careerRecErrorCard) careerRecErrorCard.classList.add('hidden');
    careerRecResultsCard.classList.remove('hidden');

    // Default to shared selected role if available, otherwise target role match, fallback to rank 1 role
    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;

    let defaultRoleId = (currentSelectedRoleId && recs.some(r => r.job_role_id === currentSelectedRoleId))
      ? currentSelectedRoleId
      : (targetRoleId || (recs.length > 0 ? recs[0].job_role_id : null));

    selectedCareerRecRoleId = defaultRoleId;
    if (!currentSelectedRoleId && defaultRoleId) {
      currentSelectedRoleId = defaultRoleId;
    }

    // 1. Populate selector buttons (Target Role First + Top 5 Alternatives + More/Less)
    renderCareerRecButtons();

    // 2. Render details for selected role
    if (selectedCareerRecRoleId) {
      renderSelectedCareerRecDetail(selectedCareerRecRoleId);
    }
  }

  function renderCareerRecButtons() {
    if (!careerRecRoleSelectorList || !currentCareerRecData || !currentCareerRecData.recommendations) return;

    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;
    const displayedRecs = buildSectionRoleDisplayList(
      currentCareerRecData.recommendations,
      isExpandedCareerRec,
      targetRoleId,
      selectedCareerRecRoleId
    );

    careerRecRoleSelectorList.innerHTML = '';
    displayedRecs.forEach(rec => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-role-id', String(rec.job_role_id));
      btn.className = (rec.job_role_id === selectedCareerRecRoleId) ? 'btn btn-primary' : 'btn btn-secondary';
      btn.style.fontSize = '0.82rem';
      btn.style.padding = '6px 12px';

      if (targetRoleId && rec.job_role_id === targetRoleId) {
        const targetBadge = document.createElement('span');
        targetBadge.className = 'role-target-badge';
        targetBadge.textContent = 'Target';
        btn.appendChild(targetBadge);
      } else {
        const rankBadge = document.createElement('span');
        rankBadge.style.fontSize = '0.72rem';
        rankBadge.style.fontWeight = '700';
        rankBadge.style.marginRight = '6px';
        rankBadge.textContent = `#${rec.rank}`;
        btn.appendChild(rankBadge);
      }

      const titleSpan = document.createElement('span');
      titleSpan.textContent = formatJobRoleTitle(rec.job_role_title);
      btn.appendChild(titleSpan);

      const fitInfo = formatFitLevel(rec.fit_level);
      const scoreBadge = document.createElement('span');
      scoreBadge.style.fontSize = '0.72rem';
      scoreBadge.style.fontWeight = '700';
      scoreBadge.style.opacity = '0.9';
      scoreBadge.style.marginLeft = '6px';
      scoreBadge.textContent = `${rec.match_percentage.toFixed(1)}% (${fitInfo.text})`;
      btn.appendChild(scoreBadge);

      btn.addEventListener('click', () => {
        selectCareerRole(rec.job_role_id, { source: 'career-recommendations' });
      });

      careerRecRoleSelectorList.appendChild(btn);
    });

    // More / Less Toggle Button
    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.className = 'btn btn-secondary more-toggle-btn';
    moreBtn.textContent = isExpandedCareerRec ? 'Less ▴' : 'More ▾';
    moreBtn.title = isExpandedCareerRec ? 'Show top roles' : 'Show all 18 roles';
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      isExpandedCareerRec = !isExpandedCareerRec;
      renderCareerRecButtons();
    });
    careerRecRoleSelectorList.appendChild(moreBtn);
  }

  async function fetchAndRenderCareerRecommendations(resumeId) {
    if (!resumeId) {
      resetCareerRecommendationsState();
      return;
    }

    // Reuse cached results if already available for this exact resume
    if (currentCareerRecData && currentCareerRecData.resume_id === resumeId) {
      renderCareerRecommendations(currentCareerRecData);
      return;
    }

    if (isCareerRecAnalyzing) {
      return; // prevent duplicate concurrent generation runs
    }

    const requestId = ++currentCareerRecRequestId;

    // Show loading state, hide empty, error, and results
    if (careerRecEmptyCard) careerRecEmptyCard.classList.add('hidden');
    if (careerRecErrorCard) careerRecErrorCard.classList.add('hidden');
    if (careerRecResultsCard) careerRecResultsCard.classList.add('hidden');
    if (careerRecLoadingCard) careerRecLoadingCard.classList.remove('hidden');

    try {
      // 1. Attempt GET first
      let getRes;
      try {
        getRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/career-recommendations`, {
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Career Recommendations API at ${API_BASE_URL}. Ensure backend is active.`);
      }

      if (requestId !== currentCareerRecRequestId) return;

      if (getRes.ok) {
        const data = await getRes.json();
        if (requestId !== currentCareerRecRequestId) return;
        if (careerRecLoadingCard) careerRecLoadingCard.classList.add('hidden');
        renderCareerRecommendations(data);
        return;
      }

      // Check if GET 404 indicates recommendations have not been generated yet
      let needsGeneration = false;
      let errDetail = '';
      try {
        const errJson = await getRes.json();
        errDetail = errJson.detail || '';
      } catch (_) {}

      // Backend returns 404 with "not been generated" or "analyze first" when recommendations do not exist yet
      if (getRes.status === 404 && (
        errDetail.toLowerCase().includes('not been generated') ||
        errDetail.toLowerCase().includes('analyze first')
      )) {
        needsGeneration = true;
      }

      if (!needsGeneration) {
        // Do NOT treat unrelated server errors (400 unanalyzed resume, 404 nonexistent resume, 500) as needing generation
        throw new Error(errDetail || `Career recommendations retrieval failed with HTTP ${getRes.status}`);
      }

      // 2. Recommendations need generation: call POST /api/resumes/{resume_id}/career-recommendations/analyze
      isCareerRecAnalyzing = true;
      let postRes;
      try {
        postRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/career-recommendations/analyze`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Career Recommendations Analysis endpoint at ${API_BASE_URL}.`);
      } finally {
        isCareerRecAnalyzing = false;
      }

      if (requestId !== currentCareerRecRequestId) return;

      if (!postRes.ok) {
        const postErrJson = await postRes.json().catch(() => ({}));
        throw new Error(postErrJson.detail || `Career recommendations generation failed with HTTP ${postRes.status}`);
      }

      const generatedData = await postRes.json();
      if (requestId !== currentCareerRecRequestId) return;

      if (careerRecLoadingCard) careerRecLoadingCard.classList.add('hidden');
      renderCareerRecommendations(generatedData);

    } catch (err) {
      if (requestId !== currentCareerRecRequestId) return;

      if (careerRecLoadingCard) careerRecLoadingCard.classList.add('hidden');
      if (careerRecResultsCard) careerRecResultsCard.classList.add('hidden');
      if (careerRecErrorCard) {
        if (careerRecErrorMessage) {
          careerRecErrorMessage.textContent = err.message || 'Failed to process career recommendations.';
        }
        careerRecErrorCard.classList.remove('hidden');
      }
    }
  }

  if (careerRecRetryBtn) {
    careerRecRetryBtn.addEventListener('click', () => {
      if (currentResumeId) {
        fetchAndRenderCareerRecommendations(currentResumeId);
      }
    });
  }

  // -------------------------------------------------------------------------
  // 4e. Learning Resources & Certifications Section Integration
  // -------------------------------------------------------------------------

  function isValidHttpUrl(string) {
    if (!string || typeof string !== 'string') return false;
    try {
      const url = new URL(string);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
      return false;
    }
  }

  function formatDifficulty(level) {
    if (!level) return '';
    switch (level.toUpperCase()) {
      case 'BEGINNER': return 'Beginner';
      case 'INTERMEDIATE': return 'Intermediate';
      case 'ADVANCED': return 'Advanced';
      default: return level.charAt(0).toUpperCase() + level.slice(1).toLowerCase();
    }
  }

  function formatResourceType(type) {
    if (!type) return '';
    switch (type.toUpperCase()) {
      case 'DOCUMENTATION': return 'Official Documentation';
      case 'COURSE': return 'Interactive Course';
      case 'TUTORIAL': return 'Step-by-Step Tutorial';
      case 'BOOK': return 'Reference Book';
      default: return type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
    }
  }

  function formatCertLevel(level) {
    if (!level) return '';
    switch (level.toUpperCase()) {
      case 'FOUNDATIONAL': return 'Foundational Level';
      case 'ASSOCIATE': return 'Associate Level';
      case 'PROFESSIONAL': return 'Professional Level';
      case 'SPECIALTY': return 'Specialty Credential';
      default: return level.charAt(0).toUpperCase() + level.slice(1).toLowerCase();
    }
  }

  function applyResourceFilter(filter) {
    selectedResourceRecFilter = filter;

    if (resourceRecFilterAllBtn && resourceRecFilterResourcesBtn && resourceRecFilterCertificationsBtn) {
      resourceRecFilterAllBtn.className = (filter === 'all') ? 'btn btn-primary' : 'btn btn-secondary';
      resourceRecFilterResourcesBtn.className = (filter === 'resources') ? 'btn btn-primary' : 'btn btn-secondary';
      resourceRecFilterCertificationsBtn.className = (filter === 'certifications') ? 'btn btn-primary' : 'btn btn-secondary';
    }

    if (resourceRecLearningSection) {
      if (filter === 'all' || filter === 'resources') {
        resourceRecLearningSection.classList.remove('hidden');
      } else {
        resourceRecLearningSection.classList.add('hidden');
      }
    }

    if (resourceRecCertSection) {
      if (filter === 'all' || filter === 'certifications') {
        resourceRecCertSection.classList.remove('hidden');
      } else {
        resourceRecCertSection.classList.add('hidden');
      }
    }
  }

  if (resourceRecFilterAllBtn) {
    resourceRecFilterAllBtn.addEventListener('click', () => applyResourceFilter('all'));
  }
  if (resourceRecFilterResourcesBtn) {
    resourceRecFilterResourcesBtn.addEventListener('click', () => applyResourceFilter('resources'));
  }
  if (resourceRecFilterCertificationsBtn) {
    resourceRecFilterCertificationsBtn.addEventListener('click', () => applyResourceFilter('certifications'));
  }

  function resetResourceRecommendationsState() {
    currentResourceRecRequestId++;
    currentResourceRecData = null;
    selectedResourceRecRoleId = null;
    selectedResourceRecFilter = 'all';

    if (resourceRecLoadingCard) resourceRecLoadingCard.classList.add('hidden');
    if (resourceRecErrorCard) resourceRecErrorCard.classList.add('hidden');
    if (resourceRecResultsCard) resourceRecResultsCard.classList.add('hidden');
    if (resourceRecEmptyCard) resourceRecEmptyCard.classList.remove('hidden');

    applyResourceFilter('all');
  }

  function renderSelectedResourceRecDetail(jobRoleId) {
    if (!currentResourceRecData || !currentResourceRecData.roles || currentResourceRecData.roles.length === 0) return;

    selectedResourceRecRoleId = jobRoleId;
    const roleItem = currentResourceRecData.roles.find(r => r.job_role_id === jobRoleId) || currentResourceRecData.roles[0];

    // 1. Update active tab style on selector buttons
    if (resourceRecRoleSelectorList) {
      const buttons = resourceRecRoleSelectorList.querySelectorAll('button');
      buttons.forEach(btn => {
        if (btn.classList.contains('more-toggle-btn')) return;
        const btnRoleId = parseInt(btn.getAttribute('data-role-id'), 10);
        if (btnRoleId === roleItem.job_role_id) {
          btn.className = 'btn btn-primary';
        } else {
          btn.className = 'btn btn-secondary';
        }
      });
    }

    const totalResCount = roleItem.learning_resources ? roleItem.learning_resources.length : (roleItem.total_resources || 0);
    const totalCertCount = roleItem.certifications ? roleItem.certifications.length : (roleItem.total_certifications || 0);

    // Header badge
    if (resourceRecHeaderBadge) {
      let rankPrefix = '';
      if (currentMatchingData && currentMatchingData.matches && currentMatchingData.matches.length > 0) {
        const mIdx = currentMatchingData.matches.findIndex(m => m.job_role_id === roleItem.job_role_id);
        if (mIdx >= 0) {
          rankPrefix = `Rank #${mIdx + 1} • `;
        }
      }
      const targetMatch = getTargetRoleMatch();
      const isTarget = targetMatch && roleItem.job_role_id === targetMatch.job_role_id;
      const targetPrefix = isTarget ? 'Target Role • ' : '';
      resourceRecHeaderBadge.textContent = `${targetPrefix}${rankPrefix}${totalResCount} Resources, ${totalCertCount} Certifications`;
    }

    // 2. Meta items
    if (resRoleTitle) resRoleTitle.textContent = formatJobRoleTitle(roleItem.job_role_title);
    if (resMatchScoreValue) {
      resMatchScoreValue.textContent = `${(roleItem.compatibility_score || 0).toFixed(1)}%`;
    }

    if (resTotalResourcesCount) resTotalResourcesCount.textContent = String(totalResCount);
    if (resTotalCertificationsCount) resTotalCertificationsCount.textContent = String(totalCertCount);

    // 3. Section count badges
    if (resourceRecLearningCountBadge) {
      resourceRecLearningCountBadge.textContent = `(${totalResCount})`;
    }
    if (resourceRecCertCountBadge) {
      resourceRecCertCountBadge.textContent = `(${totalCertCount})`;
    }

    // 4. Render Learning Resources List
    if (resourceRecLearningList) {
      resourceRecLearningList.innerHTML = '';
      if (roleItem.learning_resources && roleItem.learning_resources.length > 0) {
        roleItem.learning_resources.forEach(res => {
          const itemCard = document.createElement('div');
          itemCard.className = 'entity-item-card';

          const header = document.createElement('div');
          header.className = 'entity-item-header';

          const titleContainer = document.createElement('div');
          titleContainer.style.display = 'flex';
          titleContainer.style.alignItems = 'center';
          titleContainer.style.gap = '8px';
          titleContainer.style.flexWrap = 'wrap';

          if (isValidHttpUrl(res.url)) {
            const link = document.createElement('a');
            link.href = res.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'entity-item-title';
            link.style.color = 'var(--accent-purple)';
            link.style.textDecoration = 'none';
            link.textContent = res.title;

            const extIcon = document.createElement('span');
            extIcon.style.fontSize = '0.75rem';
            extIcon.style.marginLeft = '4px';
            extIcon.textContent = '↗';
            link.appendChild(extIcon);

            titleContainer.appendChild(link);
          } else {
            const titleSpan = document.createElement('span');
            titleSpan.className = 'entity-item-title';
            titleSpan.textContent = res.title;
            titleContainer.appendChild(titleSpan);
          }

          header.appendChild(titleContainer);

          const badgesContainer = document.createElement('div');
          badgesContainer.style.display = 'flex';
          badgesContainer.style.gap = '6px';
          badgesContainer.style.alignItems = 'center';
          badgesContainer.style.flexWrap = 'wrap';

          // Gap priority badge
          const gapBadge = document.createElement('span');
          gapBadge.className = 'skill-chip-source';
          if (res.gap_priority === 'CRITICAL_MISSING') {
            gapBadge.style.color = '#ef4444';
            gapBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
            gapBadge.textContent = 'Critical Gap';
          } else {
            gapBadge.style.color = '#f59e0b';
            gapBadge.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
            gapBadge.textContent = 'Secondary Gap';
          }
          badgesContainer.appendChild(gapBadge);

          // Free / Paid badge
          const costBadge = document.createElement('span');
          costBadge.className = 'skill-chip-source';
          if (res.is_free) {
            costBadge.style.color = 'var(--color-mint, #10b981)';
            costBadge.style.backgroundColor = 'var(--color-mint-light, rgba(16, 185, 129, 0.1))';
            costBadge.textContent = 'Free';
          } else {
            costBadge.style.color = 'var(--text-muted, #6b7280)';
            costBadge.style.backgroundColor = 'var(--bg-card-subtle, rgba(107, 114, 128, 0.1))';
            costBadge.textContent = 'Paid';
          }
          badgesContainer.appendChild(costBadge);

          // Difficulty badge
          if (res.difficulty_level) {
            const diffBadge = document.createElement('span');
            diffBadge.className = 'entity-item-badge';
            diffBadge.textContent = formatDifficulty(res.difficulty_level);
            badgesContainer.appendChild(diffBadge);
          }

          header.appendChild(badgesContainer);
          itemCard.appendChild(header);

          // Subtitle: Platform • Resource Type • Targeted Skill
          const subtitle = document.createElement('div');
          subtitle.className = 'entity-item-subtitle';
          const subParts = [];
          if (res.platform_name) subParts.push(res.platform_name);
          if (res.resource_type) subParts.push(formatResourceType(res.resource_type));
          if (res.targeted_skill_name) subParts.push(`Targeted Skill: ${res.targeted_skill_name}`);
          subtitle.textContent = subParts.join(' • ');
          itemCard.appendChild(subtitle);

          resourceRecLearningList.appendChild(itemCard);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No specific learning resources mapped for this role\'s missing skills.';
        resourceRecLearningList.appendChild(emptyNotice);
      }
    }

    // 5. Render Certifications List
    if (resourceRecCertList) {
      resourceRecCertList.innerHTML = '';
      if (roleItem.certifications && roleItem.certifications.length > 0) {
        roleItem.certifications.forEach(cert => {
          const certCard = document.createElement('div');
          certCard.className = 'entity-item-card';

          const header = document.createElement('div');
          header.className = 'entity-item-header';

          const titleContainer = document.createElement('div');
          titleContainer.style.display = 'flex';
          titleContainer.style.alignItems = 'center';
          titleContainer.style.gap = '8px';
          titleContainer.style.flexWrap = 'wrap';

          if (isValidHttpUrl(cert.official_url)) {
            const link = document.createElement('a');
            link.href = cert.official_url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'entity-item-title';
            link.style.color = 'var(--accent-purple)';
            link.style.textDecoration = 'none';
            link.textContent = cert.name;

            const extIcon = document.createElement('span');
            extIcon.style.fontSize = '0.75rem';
            extIcon.style.marginLeft = '4px';
            extIcon.textContent = '↗';
            link.appendChild(extIcon);

            titleContainer.appendChild(link);
          } else {
            const titleSpan = document.createElement('span');
            titleSpan.className = 'entity-item-title';
            titleSpan.textContent = cert.name;
            titleContainer.appendChild(titleSpan);
          }

          header.appendChild(titleContainer);

          const badgesContainer = document.createElement('div');
          badgesContainer.style.display = 'flex';
          badgesContainer.style.gap = '6px';
          badgesContainer.style.alignItems = 'center';
          badgesContainer.style.flexWrap = 'wrap';

          // Gap priority badge
          const gapBadge = document.createElement('span');
          gapBadge.className = 'skill-chip-source';
          if (cert.gap_priority === 'CRITICAL_MISSING') {
            gapBadge.style.color = '#ef4444';
            gapBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
            gapBadge.textContent = 'Critical Gap';
          } else {
            gapBadge.style.color = '#f59e0b';
            gapBadge.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
            gapBadge.textContent = 'Secondary Gap';
          }
          badgesContainer.appendChild(gapBadge);

          // Code badge (if any)
          if (cert.code) {
            const codeBadge = document.createElement('span');
            codeBadge.className = 'skill-chip-source';
            codeBadge.style.color = 'var(--accent-cyan, #06b6d4)';
            codeBadge.style.backgroundColor = 'var(--accent-cyan-light, rgba(6, 182, 212, 0.1))';
            codeBadge.style.border = '1px solid var(--accent-cyan-border, rgba(6, 182, 212, 0.2))';
            codeBadge.textContent = cert.code;
            badgesContainer.appendChild(codeBadge);
          }

          // Level badge
          if (cert.level) {
            const levelBadge = document.createElement('span');
            levelBadge.className = 'entity-item-badge';
            levelBadge.textContent = formatCertLevel(cert.level);
            badgesContainer.appendChild(levelBadge);
          }

          header.appendChild(badgesContainer);
          certCard.appendChild(header);

          // Subtitle: Provider • Targeted Skill
          const subtitle = document.createElement('div');
          subtitle.className = 'entity-item-subtitle';
          const subParts = [];
          if (cert.provider_name) subParts.push(cert.provider_name);
          if (cert.targeted_skill_name) subParts.push(`Targeted Skill: ${cert.targeted_skill_name}`);
          subtitle.textContent = subParts.join(' • ');
          certCard.appendChild(subtitle);

          // Rationale description
          if (cert.rationale) {
            const desc = document.createElement('div');
            desc.className = 'entity-item-desc';
            desc.textContent = cert.rationale;
            certCard.appendChild(desc);
          }

          resourceRecCertList.appendChild(certCard);
        });
      } else {
        const emptyNotice = document.createElement('p');
        emptyNotice.className = 'empty-entity-notice';
        emptyNotice.textContent = 'No specific industry certifications mapped for this role\'s missing skills.';
        resourceRecCertList.appendChild(emptyNotice);
      }
    }

    // 6. Apply filter to adjust visibility
    applyResourceFilter(selectedResourceRecFilter);
  }

  function renderResourceRecommendations(data) {
    if (!resourceRecResultsCard) return;

    currentResourceRecData = data;
    const roles = data.roles || [];

    if (roles.length === 0) {
      resetResourceRecommendationsState();
      return;
    }

    // Hide empty, loading, error states; show results
    if (resourceRecEmptyCard) resourceRecEmptyCard.classList.add('hidden');
    if (resourceRecLoadingCard) resourceRecLoadingCard.classList.add('hidden');
    if (resourceRecErrorCard) resourceRecErrorCard.classList.add('hidden');
    resourceRecResultsCard.classList.remove('hidden');

    // Header badge
    if (resourceRecHeaderBadge) {
      resourceRecHeaderBadge.textContent = `${data.total_resources || 0} Resources • ${data.total_certifications || 0} Certifications`;
    }

    // Choose default role: prioritize shared selected role, then target role match, then first role
    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;

    let defaultRoleId = (currentSelectedRoleId && roles.some(r => r.job_role_id === currentSelectedRoleId))
      ? currentSelectedRoleId
      : (targetRoleId || (currentMatchingData && currentMatchingData.matches && currentMatchingData.matches[0].job_role_id) || roles[0].job_role_id);

    selectedResourceRecRoleId = defaultRoleId;
    if (!currentSelectedRoleId && defaultRoleId) {
      currentSelectedRoleId = defaultRoleId;
    }

    // Populate role selector buttons (Target Role First + Top 5 Alternatives + More/Less)
    renderResourceRecButtons();

    if (selectedResourceRecRoleId) {
      renderSelectedResourceRecDetail(selectedResourceRecRoleId);
    }
  }

  function renderResourceRecButtons() {
    if (!resourceRecRoleSelectorList || !currentResourceRecData || !currentResourceRecData.roles) return;

    const targetMatch = getTargetRoleMatch();
    const targetRoleId = targetMatch ? targetMatch.job_role_id : null;
    const displayedRoles = buildSectionRoleDisplayList(
      currentResourceRecData.roles,
      isExpandedResourceRec,
      targetRoleId,
      selectedResourceRecRoleId
    );

    resourceRecRoleSelectorList.innerHTML = '';
    displayedRoles.forEach(roleItem => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-role-id', String(roleItem.job_role_id));
      btn.className = (roleItem.job_role_id === selectedResourceRecRoleId) ? 'btn btn-primary' : 'btn btn-secondary';
      btn.style.fontSize = '0.82rem';
      btn.style.padding = '6px 12px';

      if (targetRoleId && roleItem.job_role_id === targetRoleId) {
        const targetBadge = document.createElement('span');
        targetBadge.className = 'role-target-badge';
        targetBadge.textContent = 'Target';
        btn.appendChild(targetBadge);
      }

      const titleSpan = document.createElement('span');
      titleSpan.textContent = formatJobRoleTitle(roleItem.job_role_title);
      btn.appendChild(titleSpan);

      const rCount = roleItem.learning_resources ? roleItem.learning_resources.length : (roleItem.total_resources || 0);
      const cCount = roleItem.certifications ? roleItem.certifications.length : (roleItem.total_certifications || 0);

      const countBadge = document.createElement('span');
      countBadge.style.fontSize = '0.72rem';
      countBadge.style.fontWeight = '700';
      countBadge.style.opacity = '0.9';
      countBadge.style.marginLeft = '6px';
      countBadge.textContent = `(${rCount + cCount})`;
      btn.appendChild(countBadge);

      btn.addEventListener('click', () => {
        selectCareerRole(roleItem.job_role_id, { source: 'learning-resources' });
      });

      resourceRecRoleSelectorList.appendChild(btn);
    });

    // More / Less Toggle Button
    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.className = 'btn btn-secondary more-toggle-btn';
    moreBtn.textContent = isExpandedResourceRec ? 'Less ▴' : 'More ▾';
    moreBtn.title = isExpandedResourceRec ? 'Show top roles' : 'Show all 18 roles';
    moreBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      isExpandedResourceRec = !isExpandedResourceRec;
      renderResourceRecButtons();
    });
    resourceRecRoleSelectorList.appendChild(moreBtn);
  }

  async function fetchAndRenderResourceRecommendations(resumeId) {
    if (!resumeId) {
      resetResourceRecommendationsState();
      return;
    }

    // Reuse cached results if already available for this exact resume
    if (currentResourceRecData && currentResourceRecData.resume_id === resumeId) {
      renderResourceRecommendations(currentResourceRecData);
      return;
    }

    if (isResourceRecAnalyzing) {
      return; // prevent duplicate concurrent generation runs
    }

    const requestId = ++currentResourceRecRequestId;

    // Show loading state, hide empty, error, and results
    if (resourceRecEmptyCard) resourceRecEmptyCard.classList.add('hidden');
    if (resourceRecErrorCard) resourceRecErrorCard.classList.add('hidden');
    if (resourceRecResultsCard) resourceRecResultsCard.classList.add('hidden');
    if (resourceRecLoadingCard) resourceRecLoadingCard.classList.remove('hidden');

    try {
      // 1. Attempt GET first (read-only)
      let getRes;
      try {
        getRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/resource-recommendations`, {
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Resource Recommendations API at ${API_BASE_URL}. Ensure backend is active.`);
      }

      if (requestId !== currentResourceRecRequestId) return;

      if (getRes.ok) {
        const data = await getRes.json();
        if (requestId !== currentResourceRecRequestId) return;
        if (resourceRecLoadingCard) resourceRecLoadingCard.classList.add('hidden');
        renderResourceRecommendations(data);
        return;
      }

      // Check if GET 404 indicates recommendations have not been generated yet
      let needsGeneration = false;
      let errDetail = '';
      try {
        const errJson = await getRes.json();
        errDetail = errJson.detail || '';
      } catch (_) {}

      if (getRes.status === 404 && (
        errDetail.toLowerCase().includes('not been generated') ||
        errDetail.toLowerCase().includes('analyze first')
      )) {
        needsGeneration = true;
      }

      if (!needsGeneration) {
        throw new Error(errDetail || `Resource recommendations retrieval failed with HTTP ${getRes.status}`);
      }

      // 2. Recommendations need generation: call POST /api/resumes/{resume_id}/resource-recommendations/analyze
      isResourceRecAnalyzing = true;
      let postRes;
      try {
        postRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/resource-recommendations/analyze`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to Resource Recommendations Analysis endpoint at ${API_BASE_URL}.`);
      } finally {
        isResourceRecAnalyzing = false;
      }

      if (requestId !== currentResourceRecRequestId) return;

      if (!postRes.ok) {
        const postErrJson = await postRes.json().catch(() => ({}));
        throw new Error(postErrJson.detail || `Resource recommendations generation failed with HTTP ${postRes.status}`);
      }

      const generatedData = await postRes.json();
      if (requestId !== currentResourceRecRequestId) return;

      if (resourceRecLoadingCard) resourceRecLoadingCard.classList.add('hidden');
      renderResourceRecommendations(generatedData);

    } catch (err) {
      if (requestId !== currentResourceRecRequestId) return;

      if (resourceRecLoadingCard) resourceRecLoadingCard.classList.add('hidden');
      if (resourceRecResultsCard) resourceRecResultsCard.classList.add('hidden');
      if (resourceRecErrorCard) {
        if (resourceRecErrorMessage) {
          resourceRecErrorMessage.textContent = err.message || 'Failed to process resource recommendations.';
        }
        resourceRecErrorCard.classList.remove('hidden');
      }
    }
  }

  if (resourceRecRetryBtn) {
    resourceRecRetryBtn.addEventListener('click', () => {
      if (currentResumeId) {
        fetchAndRenderResourceRecommendations(currentResumeId);
      }
    });
  }

  analyzeBtn.addEventListener('click', async () => {
    hideUploadError();
    hideStatusMessage();

    const hasFile = currentFile !== null;
    if (!hasFile) {
      showStatusMessage(
        'warning',
        '⚠️',
        '<strong>Resume File Missing:</strong> Please select or drop a valid PDF or DOCX resume before running analysis.'
      );
      return;
    }

    // Enter loading state
    const originalBtnHtml = analyzeBtn.innerHTML;
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<span>Uploading & Analyzing...</span> <span class="spinner">⏳</span>';

    // Reset list expansion states for fresh analysis run
    isExpandedJobMatching = false;
    isExpandedSkillGap = false;
    isExpandedCareerRec = false;
    isExpandedResourceRec = false;

    try {
      // Step 1: Upload resume to FastAPI backend
      const formData = new FormData();
      formData.append('file', currentFile);

      let uploadRes;
      try {
        uploadRes = await fetch(`${API_BASE_URL}/api/resumes/upload`, {
          method: 'POST',
          body: formData,
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to CareerSync API at ${API_BASE_URL}. Please ensure the backend server is running.`);
      }

      if (!uploadRes.ok) {
        const errJson = await uploadRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with HTTP status ${uploadRes.status}`);
      }

      const uploadData = await uploadRes.json();
      currentResumeToken = uploadData.access_token || null;

      // Check if text extraction succeeded
      if (uploadData.parsing_status === 'FAILED') {
        currentResumeId = null;
        currentResumeToken = null;
        resetJobMatchingState();
        resetSkillGapState();
        resetCareerRecommendationsState();
        resetResourceRecommendationsState();
        showStatusMessage(
          'warning',
          '⚠️',
          `<strong>Extraction Incomplete:</strong> ${uploadData.message || 'No readable text could be extracted.'}`
        );
        overviewResumeStatus.textContent = 'Failed';
        if (extractedProfileCard) extractedProfileCard.classList.add('hidden');
        return;
      }

      // Step 2: Trigger transactional analysis
      const resumeId = uploadData.id;
      let analyzeRes;
      try {
        analyzeRes = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/analyze`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        currentResumeId = null;
        currentResumeToken = null;
        resetJobMatchingState();
        resetSkillGapState();
        resetCareerRecommendationsState();
        resetResourceRecommendationsState();
        throw new Error(`Connection to backend interrupted during analysis: ${netErr.message}`);
      }

      if (!analyzeRes.ok) {
        currentResumeId = null;
        currentResumeToken = null;
        resetJobMatchingState();
        resetSkillGapState();
        resetCareerRecommendationsState();
        resetResourceRecommendationsState();
        overviewResumeStatus.textContent = 'Analysis Failed';
        overviewResumeStatus.classList.add('stat-muted');
        const errJson = await analyzeRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Analysis failed with HTTP status ${analyzeRes.status}`);
      }

      const analysisData = await analyzeRes.json();

      // Successfully completed analysis — assign and retain state for subsequent stages
      currentResumeId = resumeId;

      // Step 3: Render extracted profile
      renderExtractedProfile(analysisData);

      // Step 4: Update Overview Dashboard Card
      overviewResumeStatus.textContent = 'Analyzed';
      overviewResumeStatus.classList.remove('stat-muted');
      updateDashboardOverview();

      showStatusMessage(
        'success',
        '✅',
        `<strong>Resume Analyzed Successfully:</strong> Verified <strong>${analysisData.skills.length}</strong> catalog skills, ${analysisData.education.length} education records, ${analysisData.projects.length} projects, and ${analysisData.experience.length} experience entries.`
      );

      // Step 5: Automatically fetch and render Job Role Matching for currentResumeId
      await fetchAndRenderJobMatching(currentResumeId);

      // Step 6: Automatically fetch and render Skill Gap Analysis for currentResumeId
      await fetchAndRenderSkillGaps(currentResumeId);

      // Step 7: Automatically fetch and render Career Recommendations for currentResumeId
      await fetchAndRenderCareerRecommendations(currentResumeId);

      // Step 8: Automatically fetch and render Learning Resources & Certifications for currentResumeId
      await fetchAndRenderResourceRecommendations(currentResumeId);

    } catch (err) {
      currentResumeId = null;
      resetJobMatchingState();
      resetSkillGapState();
      resetCareerRecommendationsState();
      resetResourceRecommendationsState();
      if (overviewResumeStatus.textContent !== 'Failed') {
        overviewResumeStatus.textContent = 'Analysis Failed';
        overviewResumeStatus.classList.add('stat-muted');
      }
      showStatusMessage('warning', '⚠️', `<strong>Operation Error:</strong> ${err.message}`);
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.innerHTML = originalBtnHtml;
    }
  });

  // -------------------------------------------------------------------------
  // 5. Sidebar Navigation, View Switching & Scroll-Spy
  // -------------------------------------------------------------------------
  let isClickScrolling = false;
  let clickScrollTimeout = null;

  function setActiveLink(sectionId) {
    if (!sectionId) return;

    // Clear settings active state when highlighting a dashboard section
    if (settingsNavLink) {
      settingsNavLink.classList.remove('active');
    }

    navLinks.forEach(link => {
      if (link.getAttribute('data-section') === sectionId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  /**
   * Switch between Dashboard and Settings views
   */
  function switchView(targetView, targetSectionId = null) {
    if (targetView === 'settings') {
      currentView = 'settings';
      if (dashboardView) dashboardView.classList.add('hidden');
      if (settingsView) settingsView.classList.remove('hidden');

      if (topBarTitle && topBarSubtitle) {
        topBarTitle.textContent = 'Settings';
        topBarSubtitle.textContent = 'Manage your workspace visual preferences and review application details.';
      }

      navLinks.forEach(l => l.classList.remove('active'));
      if (settingsNavLink) {
        settingsNavLink.classList.add('active');
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });

      if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
      }
    } else {
      currentView = 'dashboard';
      if (settingsView) settingsView.classList.add('hidden');
      if (dashboardView) dashboardView.classList.remove('hidden');

      if (topBarTitle && topBarSubtitle) {
        topBarTitle.textContent = 'Resume-Based Career and Resource Recommendation System';
        topBarSubtitle.textContent = 'Analyze resumes against target roles to identify skill gaps, career paths, and tailored learning resources.';
      }

      if (settingsNavLink) {
        settingsNavLink.classList.remove('active');
      }

      if (targetSectionId) {
        const targetElement = document.getElementById(targetSectionId);
        if (targetElement) {
          setActiveLink(targetSectionId);
          isClickScrolling = true;
          clearTimeout(clickScrollTimeout);

          targetElement.scrollIntoView({ behavior: 'smooth' });

          clickScrollTimeout = setTimeout(() => {
            isClickScrolling = false;
          }, 800);
        }
      } else {
        updateActiveSection();
      }

      if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
      }
    }
  }

  // Settings nav link click
  if (settingsNavLink) {
    settingsNavLink.addEventListener('click', (e) => {
      e.preventDefault();
      switchView('settings');
    });
  }

  // Dashboard nav links click
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId.startsWith('#')) {
        e.preventDefault();
        const sectionId = link.getAttribute('data-section');

        if (currentView === 'settings') {
          // Returning to Dashboard from Settings
          switchView('dashboard', sectionId);
        } else {
          // Trigger on-demand data fetch if active resume exists but section data not yet populated
          if (sectionId === 'job-matching' && currentResumeId && !currentMatchingData) {
            fetchAndRenderJobMatching(currentResumeId);
          } else if (sectionId === 'skill-gap' && currentResumeId && !currentSkillGapData && !isSkillGapAnalyzing) {
            fetchAndRenderSkillGaps(currentResumeId);
          } else if (sectionId === 'career-recommendations' && currentResumeId && !currentCareerRecData && !isCareerRecAnalyzing) {
            fetchAndRenderCareerRecommendations(currentResumeId);
          } else if (sectionId === 'learning-resources' && currentResumeId && !currentResourceRecData && !isResourceRecAnalyzing) {
            fetchAndRenderResourceRecommendations(currentResumeId);
          }

          // Already on Dashboard: smooth scroll to section
          const targetElement = document.querySelector(targetId);
          if (targetElement) {
            setActiveLink(sectionId);
            isClickScrolling = true;
            clearTimeout(clickScrollTimeout);

            targetElement.scrollIntoView({ behavior: 'smooth' });

            clickScrollTimeout = setTimeout(() => {
              isClickScrolling = false;
            }, 800);

            if (sidebar && sidebar.classList.contains('open')) {
              sidebar.classList.remove('open');
            }
          }
        }
      }
    });
  });

  // Cancel click-scrolling lock if user manually interacts
  window.addEventListener('wheel', () => { isClickScrolling = false; }, { passive: true });
  window.addEventListener('touchstart', () => { isClickScrolling = false; }, { passive: true });

  /**
   * Determine and update the active section based on scroll position
   */
  function updateActiveSection() {
    // Only track scroll-spy when viewing the Dashboard
    if (currentView !== 'dashboard') return;
    if (isClickScrolling) return;

    const scrollY = window.scrollY;
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;

    // 1. Bottom of page check: ensures the final section (Resume Improvement)
    // is always highlighted when the user scrolls to the bottom
    if (scrollY + windowHeight >= documentHeight - 50) {
      const lastSection = sections[sections.length - 1];
      if (lastSection) {
        setActiveLink(lastSection.id);
        return;
      }
    }

    // 2. Very top of page check: ensures Overview is highlighted at the top
    if (scrollY < 60) {
      const firstSection = sections[0];
      if (firstSection) {
        setActiveLink(firstSection.id);
        return;
      }
    }

    // 3. Focal point evaluation: identify which section occupies the primary reading zone
    // (140px below the top of viewport, just below top bar)
    const focalOffset = 140;
    let currentSectionId = null;

    for (let i = 0; i < sections.length; i++) {
      const rect = sections[i].getBoundingClientRect();
      if (rect.top <= focalOffset && rect.bottom > focalOffset) {
        currentSectionId = sections[i].id;
        break;
      }
    }

    // Fallback: find section with top closest to focalOffset
    if (!currentSectionId && sections.length > 0) {
      let closestSection = sections[0];
      let minDistance = Math.abs(sections[0].getBoundingClientRect().top - focalOffset);

      for (let i = 1; i < sections.length; i++) {
        const distance = Math.abs(sections[i].getBoundingClientRect().top - focalOffset);
        if (distance < minDistance) {
          minDistance = distance;
          closestSection = sections[i];
        }
      }
      currentSectionId = closestSection.id;
    }

    if (currentSectionId) {
      setActiveLink(currentSectionId);
    }
  }

  // IntersectionObserver for reactive visibility tracking
  if ('IntersectionObserver' in window) {
    const observerOptions = {
      root: null,
      rootMargin: '-10% 0px -40% 0px',
      threshold: [0, 0.25, 0.5, 0.75, 1.0]
    };

    const sectionObserver = new IntersectionObserver(() => {
      updateActiveSection();
    }, observerOptions);

    sections.forEach(sec => sectionObserver.observe(sec));
  }

  // Throttled scroll listener via requestAnimationFrame for 60fps responsiveness
  let scrollTicking = false;
  window.addEventListener('scroll', () => {
    if (!scrollTicking) {
      window.requestAnimationFrame(() => {
        updateActiveSection();
        scrollTicking = false;
      });
      scrollTicking = true;
    }
  }, { passive: true });

  window.addEventListener('resize', updateActiveSection, { passive: true });

  // Initialize active state on load
  updateActiveSection();


  /**
   * Secure Resume Deletion (Phase 1)
   * Sends DELETE request with X-Resume-Token, verifies server response,
   * and clears local browser state only upon confirmed success.
   */
  async function handleResumeDeletion() {
    if (!currentResumeId) {
      showStatusMessage('warning', '⚠️', 'No active resume found to delete.');
      return;
    }

    if (!currentResumeToken) {
      showStatusMessage('error', '❌', 'Missing authorization token for this resume session. Deletion aborted.');
      return;
    }

    const confirmed = window.confirm(
      'Are you sure you want to permanently delete your resume and all analysis data? This action cannot be undone.'
    );
    if (!confirmed) {
      return;
    }

    try {
      let deleteRes;
      try {
        deleteRes = await fetch(`${API_BASE_URL}/api/resumes/${currentResumeId}`, {
          method: 'DELETE',
          headers: getAuthHeaders(),
        });
      } catch (netErr) {
        throw new Error(`Cannot connect to CareerSync API at ${API_BASE_URL}. Server may be unreachable.`);
      }

      if (!deleteRes.ok) {
        const errJson = await deleteRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned HTTP status ${deleteRes.status}`);
      }

      const resData = await deleteRes.json();

      // Deletion confirmed by server — clear all local in-memory session state
      currentResumeId = null;
      currentResumeToken = null;
      currentFile = null;

      resetFileInput();
      resetJobMatchingState();
      resetSkillGapState();
      resetCareerRecommendationsState();
      resetResourceRecommendationsState();

      if (extractedProfileCard) {
        extractedProfileCard.classList.add('hidden');
      }

      overviewResumeStatus.textContent = 'Deleted';
      overviewResumeStatus.classList.add('stat-muted');
      updateDashboardOverview();

      showStatusMessage(
        'success',
        '✅',
        `<strong>Resume Deleted:</strong> ${resData.message || 'Your resume and all associated analysis data have been permanently removed.'}`
      );
    } catch (err) {
      // If deletion failed, do NOT clear local state and do NOT claim data was deleted
      showStatusMessage(
        'error',
        '❌',
        `<strong>Deletion Failed:</strong> ${err.message}`
      );
    }
  }

  if (deleteResumeBtn) {
    deleteResumeBtn.addEventListener('click', handleResumeDeletion);
  }

  // -------------------------------------------------------------------------
  // 6. Mobile Sidebar Toggle
  // -------------------------------------------------------------------------
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    // Close when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !mobileMenuBtn.contains(e.target)
      ) {
        sidebar.classList.remove('open');
      }
    });
  }
});
